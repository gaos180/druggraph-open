import React, { useState } from 'react';
import { User, Settings } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { usersApi } from '../api/users';
import { usePageTitle } from '../hooks/usePageTitle';
import { NotebookLayout, NotebookNavbar, HandTitle, PencilButton } from '../components/notebook';

const inputCls = 'w-full bg-[#faf6ee] px-3 py-2 border-2 border-[#3f3429] rounded-xl font-hand text-sm focus:outline-none focus:ring-1 focus:ring-stone-600 disabled:opacity-60';

function InputRow({ label, type = 'text', value, onChange, disabled = false }: {
  label: string; type?: string; value: string; onChange: (v: string) => void; disabled?: boolean;
}) {
  return (
    <div className="flex flex-col gap-1">
      <label className="text-[11px] font-mono text-stone-500">{label.toUpperCase()}</label>
      <input type={type} value={value} onChange={e => onChange(e.target.value)} disabled={disabled} className={inputCls} />
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="bg-[#faf6ee] border-2 border-stone-800/15 rounded-2xl p-6 flex flex-col gap-4 shadow-[2px_2.5px_0_rgba(30,25,21,0.06)]">
      <h3 className="font-hand font-bold text-lg text-stone-800">{title}</h3>
      {children}
    </div>
  );
}

export default function ProfilePage() {
  const { user } = useAuth();
  usePageTitle('Mi perfil');

  const [name, setName] = useState(user?.name ?? '');
  const [email, setEmail] = useState(user?.email ?? '');
  const [infoMsg, setInfoMsg] = useState<{ ok: boolean; text: string } | null>(null);
  const [savingInfo, setSavingInfo] = useState(false);
  const [curPwd, setCurPwd] = useState('');
  const [newPwd, setNewPwd] = useState('');
  const [confPwd, setConfPwd] = useState('');
  const [pwdMsg, setPwdMsg] = useState<{ ok: boolean; text: string } | null>(null);
  const [savingPwd, setSavingPwd] = useState(false);

  const handleSaveInfo = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim() || !email.trim()) { setInfoMsg({ ok: false, text: 'Nombre y correo son obligatorios.' }); return; }
    setSavingInfo(true); setInfoMsg(null);
    try {
      await usersApi.updateMe({ name: name.trim(), email: email.trim() });
      setInfoMsg({ ok: true, text: 'Datos actualizados correctamente.' });
    } catch (err: any) {
      setInfoMsg({ ok: false, text: err?.response?.data?.error ?? 'Error al guardar los cambios.' });
    } finally { setSavingInfo(false); }
  };

  const handleChangePassword = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!curPwd || !newPwd || !confPwd) { setPwdMsg({ ok: false, text: 'Completa todos los campos.' }); return; }
    if (newPwd !== confPwd) { setPwdMsg({ ok: false, text: 'Las contraseñas nuevas no coinciden.' }); return; }
    if (newPwd.length < 6) { setPwdMsg({ ok: false, text: 'La contraseña debe tener al menos 6 caracteres.' }); return; }
    setSavingPwd(true); setPwdMsg(null);
    try {
      await usersApi.changePassword(curPwd, newPwd);
      setPwdMsg({ ok: true, text: 'Contraseña actualizada correctamente.' });
      setCurPwd(''); setNewPwd(''); setConfPwd('');
    } catch (err: any) {
      setPwdMsg({ ok: false, text: err?.response?.data?.error ?? 'Error al cambiar la contraseña.' });
    } finally { setSavingPwd(false); }
  };

  const Msg = ({ m }: { m: { ok: boolean; text: string } }) => (
    <div className={`text-[13px] font-mono px-3 py-2 rounded-lg border ${m.ok ? 'text-emerald-700 bg-emerald-50 border-emerald-300' : 'text-red-700 bg-red-50 border-red-300'}`}>{m.text}</div>
  );

  return (
    <NotebookLayout navbar={<NotebookNavbar />} maxWidth="max-w-3xl">
      <div className="mb-5">
        <HandTitle className="text-3xl flex items-center gap-2"><User className="w-7 h-7 text-amber-800" /> Mi Perfil</HandTitle>
        <p className="text-sm text-stone-500 font-hand mt-1">Gestiona tu información de cuenta y contraseña.</p>
      </div>

      <div className="flex flex-col gap-5">
        <Section title="Información personal">
          <form onSubmit={handleSaveInfo} className="flex flex-col gap-3.5">
            <InputRow label="Nombre completo" value={name} onChange={setName} />
            <InputRow label="Correo electrónico" type="email" value={email} onChange={setEmail} />
            {infoMsg && <Msg m={infoMsg} />}
            <PencilButton type="submit" variant="solid" disabled={savingInfo} className="self-start">{savingInfo ? 'Guardando…' : 'Guardar cambios'}</PencilButton>
          </form>
        </Section>

        <Section title="Cambiar contraseña">
          <form onSubmit={handleChangePassword} className="flex flex-col gap-3.5">
            <InputRow label="Contraseña actual" type="password" value={curPwd} onChange={setCurPwd} />
            <InputRow label="Nueva contraseña" type="password" value={newPwd} onChange={setNewPwd} />
            <InputRow label="Confirmar nueva contraseña" type="password" value={confPwd} onChange={setConfPwd} />
            {pwdMsg && <Msg m={pwdMsg} />}
            <PencilButton type="submit" variant="solid" disabled={savingPwd} className="self-start">{savingPwd ? 'Cambiando…' : 'Cambiar contraseña'}</PencilButton>
          </form>
        </Section>

        <Section title="Información de cuenta">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            {[
              { label: 'Rol', value: user?.is_admin ? 'Administrador' : 'Usuario', icon: user?.is_admin ? <Settings className="w-4 h-4" /> : <User className="w-4 h-4" /> },
              { label: 'ID de cuenta', value: user?._id ?? '—', mono: true },
            ].map(({ label, value, icon, mono }) => (
              <div key={label} className="bg-stone-100 rounded-xl px-4 py-3">
                <div className="text-[11px] text-stone-500 mb-1 font-mono">{label.toUpperCase()}</div>
                <div className={`text-sm text-stone-800 flex items-center gap-1.5 ${mono ? 'font-mono break-all' : ''}`}>{icon}{value}</div>
              </div>
            ))}
          </div>
        </Section>
      </div>
    </NotebookLayout>
  );
}
