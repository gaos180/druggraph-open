import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import DrugsPage from './DrugsPage';
import { drugsApi } from '../../api/drugs';
import { targetsApi } from '../../api/targets';

// ── Notebook component stubs ──────────────────────────────────────────────────
// NotebookNavbar calls useAuth() + useNavigate(). Mock the whole notebook module
// so tests don't require an AuthProvider or a real Router for the navbar.
jest.mock('../../components/notebook', () => ({
  NotebookLayout: ({ children, navbar }: any) => (
    <div>
      {navbar}
      {children}
    </div>
  ),
  NotebookNavbar: () => <nav data-testid="notebook-navbar" />,
  NotebookCard: ({ children, onClick }: any) => (
    <div onClick={onClick}>{children}</div>
  ),
  HandTitle: ({ children }: any) => <h1>{children}</h1>,
  PencilButton: ({ children, onClick, disabled }: any) => (
    <button onClick={onClick} disabled={disabled}>
      {children}
    </button>
  ),
  Tag: ({ children }: any) => <span>{children}</span>,
  groupTone: () => 'blue',
  ChemicalDoodle: () => <div data-testid="chemical-doodle" />,
  SectionHeader: ({ children }: any) => <h2>{children}</h2>,
  EmptyState: ({ title }: any) => (
    <div data-testid="empty-state">{title}</div>
  ),
  Loader: ({ label }: any) => <div data-testid="loader">{label}</div>,
}));

// ── API mocks ─────────────────────────────────────────────────────────────────
jest.mock('../../api/drugs', () => ({
  drugsApi: {
    list: jest.fn(),
    filters: jest.fn(),
    detail: jest.fn(),
    graph: jest.fn(),
    adminCreate: jest.fn(),
    adminUpdate: jest.fn(),
    adminDelete: jest.fn(),
  },
}));

jest.mock('../../api/targets', () => ({
  targetsApi: {
    byGene: jest.fn(),
    list: jest.fn(),
    detail: jest.fn(),
    adminCreate: jest.fn(),
    adminUpdate: jest.fn(),
    adminDelete: jest.fn(),
    uniprot: jest.fn(),
    pathways: jest.fn(),
    keggGene: jest.fn(),
    graph: jest.fn(),
    compare: jest.fn(),
  },
}));

const mockList = drugsApi.list as jest.Mock;
const mockFilters = drugsApi.filters as jest.Mock;
// targetsApi.byGene is only triggered when the gene search input is non-empty,
// so we only need it to be a jest.fn() (no default implementation needed here).

// ── Helpers ───────────────────────────────────────────────────────────────────
const EMPTY_PAGE = {
  page: 1,
  per_page: 10,
  has_next: false,
  has_prev: false,
  results: [],
};

const DRUGS_PAGE = {
  page: 1,
  per_page: 10,
  has_next: false,
  has_prev: false,
  results: [
    {
      _id: 'db1',
      name: 'Aspirin',
      type: 'SmallMolecule',
      groups: ['approved'],
      'drugbank-id': 'DC1234',
      description: 'Pain reliever.',
    },
    {
      _id: 'db2',
      name: 'Ibuprofen',
      type: 'SmallMolecule',
      groups: ['approved'],
      'drugbank-id': 'DB01050',
      description: 'Anti-inflammatory.',
    },
  ],
};

function renderPage() {
  return render(
    <MemoryRouter>
      <DrugsPage />
    </MemoryRouter>
  );
}

// ── Tests ─────────────────────────────────────────────────────────────────────
describe('DrugsPage — búsqueda', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockFilters.mockResolvedValue({ data: { types: [], groups: [] } });
  });

  it('renders a drug name/SMILES search input', async () => {
    mockList.mockResolvedValue({ data: EMPTY_PAGE });

    renderPage();

    // The search input has placeholder "Nombre, sinónimo o SMILES…"
    expect(
      screen.getByPlaceholderText(/nombre, sinónimo/i)
    ).toBeInTheDocument();
  });

  it('search input is present in the DOM after mount', () => {
    mockList.mockResolvedValue({ data: EMPTY_PAGE });

    renderPage();

    const input = screen.getByPlaceholderText(/nombre, sinónimo/i);
    expect(input).toBeInTheDocument();
    expect(input.tagName).toBe('INPUT');
  });

  it('renders drug cards when the API responds with results', async () => {
    mockList.mockResolvedValue({ data: DRUGS_PAGE });

    renderPage();

    // findByText polls until the element appears (after loading resolves)
    expect(await screen.findByText('Aspirin')).toBeInTheDocument();
    expect(screen.getByText('Ibuprofen')).toBeInTheDocument();
  });

  it('shows empty state when the API responds with an empty list', async () => {
    mockList.mockResolvedValue({ data: EMPTY_PAGE });

    renderPage();

    const emptyEl = await screen.findByTestId('empty-state');
    expect(emptyEl).toBeInTheDocument();
    expect(emptyEl).toHaveTextContent(/no se encontraron/i);
  });
});
