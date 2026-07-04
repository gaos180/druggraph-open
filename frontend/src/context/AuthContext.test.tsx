import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { AuthProvider, useAuth } from './AuthContext';
import { authApi } from '../api/auth';

// ── Mock the auth API module ──────────────────────────────────────────────────
// AuthProvider calls authApi.me() unconditionally on every mount (cookie-based
// session restore), so we must provide a default resolved value in the factory.
const MOCK_USER_DEFAULT = { _id: '1', email: 'a@b.com', name: 'Test', is_admin: false };

jest.mock('../api/auth', () => ({
  authApi: {
    login: jest.fn(),
    register: jest.fn(),
    // Default: session is valid → me() resolves with a generic user.
    me: jest.fn().mockResolvedValue({ data: { _id: '1', email: 'a@b.com', name: 'Test', is_admin: false } }),
    // logout is called by the AuthProvider's logout() function.
    logout: jest.fn().mockResolvedValue({ data: { ok: true } }),
  },
}));

// Typed reference to the mocked module (type-only cast, same runtime object)
const mockedAuthApi = authApi as jest.Mocked<typeof authApi>;

// A JWT whose payload carries a far-future exp so decodeTokenExpiry succeeds
const MOCK_TOKEN =
  'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9' +
  '.eyJleHAiOjk5OTk5OTk5OTl9' +
  '.placeholder-sig';

const MOCK_USER = { _id: '1', email: 'a@b.com', name: 'Test', is_admin: false };

/** Minimal consumer that exposes what the context provides */
function TestConsumer() {
  const { user, login, logout } = useAuth();
  return (
    <div>
      <span data-testid="user-email">{user ? user.email : 'null'}</span>
      <button onClick={() => login('a@b.com', 'pass123')}>Login</button>
      <button onClick={() => logout()}>Logout</button>
    </div>
  );
}

function renderWithAuth() {
  return render(
    <AuthProvider>
      <TestConsumer />
    </AuthProvider>
  );
}

describe('AuthContext', () => {
  beforeEach(() => {
    localStorage.clear();
    // Restore the default me() behaviour before each test.
    // (clearAllMocks clears call history but keeps implementations.)
    jest.clearAllMocks();
    mockedAuthApi.me.mockResolvedValue({ data: MOCK_USER_DEFAULT } as any);
    mockedAuthApi.logout.mockResolvedValue({ data: { ok: true } } as any);
  });

  it('exposes user (null initially when me() succeeds with default user), login, and logout', async () => {
    // me() resolves with the default mock user — but we want to show user==null
    // before any explicit login action, so override me() to reject (not logged in).
    mockedAuthApi.me.mockRejectedValueOnce(new Error('not authenticated'));

    renderWithAuth();

    // findBy* waits for AuthProvider to finish the loading phase
    const emailEl = await screen.findByTestId('user-email');

    expect(emailEl).toHaveTextContent('null');
    expect(screen.getByRole('button', { name: 'Login' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Logout' })).toBeInTheDocument();
  });

  it('sets user to non-null after a successful login()', async () => {
    // First mount: me() fails so we start unauthenticated
    mockedAuthApi.me.mockRejectedValueOnce(new Error('not authenticated'));
    mockedAuthApi.login.mockResolvedValue({
      data: { token: MOCK_TOKEN, user: MOCK_USER },
    } as any);

    renderWithAuth();
    await screen.findByTestId('user-email');

    userEvent.click(screen.getByRole('button', { name: 'Login' }));

    await waitFor(() => {
      expect(screen.getByTestId('user-email')).toHaveTextContent('a@b.com');
    });
  });

  it('clears user and removes dg_token from localStorage after logout()', async () => {
    // Start logged in: me() succeeds → user is set automatically on mount
    // (default mock already resolves with MOCK_USER_DEFAULT, which has email a@b.com)

    renderWithAuth();
    await screen.findByTestId('user-email');
    await waitFor(() =>
      expect(screen.getByTestId('user-email')).toHaveTextContent('a@b.com')
    );

    // Perform logout
    userEvent.click(screen.getByRole('button', { name: 'Logout' }));

    await waitFor(() =>
      expect(screen.getByTestId('user-email')).toHaveTextContent('null')
    );
    expect(localStorage.getItem('dg_token')).toBeNull();
  });

  it('leaves user null when me() rejects on mount (simulates 401)', async () => {
    localStorage.setItem('dg_token', 'stale-token');
    mockedAuthApi.me.mockRejectedValueOnce(new Error('401 Unauthorized'));

    renderWithAuth();

    const emailEl = await screen.findByTestId('user-email');
    expect(emailEl).toHaveTextContent('null');
  });
});
