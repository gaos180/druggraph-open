import React, { useState, useEffect, useCallback } from 'react';
import { UserPlus, Pencil, KeyRound, Trash2, Settings, Pill, Crosshair, Plus, RefreshCw } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { usersApi, UserRecord, CreateUserParams } from '../api/users';
import { drugsApi, DrugSummary, DrugCreateParams } from '../api/drugs';
import { targetsApi, TargetRecord, TargetAdminUpdate, TargetCreateParams } from '../api/targets';
import { usePageTitle } from '../hooks/usePageTitle';
import { NotebookLayout, NotebookNavbar, HandTitle, PencilButton, Modal, Tag } from '../components/notebook';

// ── Utilidades compartidas ────────────────────────────────────────────────────

function formatDate(iso: string) {
  try { return new Date(iso).toLocaleDateString('es-ES', { day: '2-digit', month: 'short', year: 'numeric' }); }
  catch { return iso; }
}

const inputCls = 'w-full bg-[#faf6ee] border-2 border-[#3f3429] rounded-lg px-3 py-2 text-sm font-hand outline-none focus:ring-1 focus:ring-stone-600';
const labelCls = 'block text-[11px] font-mono text-stone-500 mb-1';
const th = 'px-4 py-3 text-left text-stone-500 text-[11px] font-bold uppercase tracking-wider font-mono';
const td = 'px-4 py-3 text-sm';
const iconBtn = 'p-1.5 rounded-lg border-2 cursor-pointer transition-colors';

const ErrBox = ({ msg }: { msg: string }) => (
  <div className="bg-red-50 border border-red-300 text-red-700 px-3 py-2 rounded-lg text-[13px]">⚠ {msg}</div>
);

function DeleteConfirmModal({ title, name, onClose, onConfirm }: {
  title: string; name: string; onClose: () => void; onConfirm: () => Promise<void>;
}) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const handle = async () => {
    setLoading(true);
    try { await onConfirm(); }
    catch (e: any) { setError(e?.response?.data?.error || 'Error al eliminar.'); setLoading(false); }
  };
  return (
    <Modal open onClose={onClose} title={title} maxWidth="max-w-sm">
      <p className="text-stone-700 text-sm mb-4">¿Eliminar <strong>{name}</strong>? Esta acción no se puede deshacer.</p>
      {error && <div className="mb-3"><ErrBox msg={error} /></div>}
      <div className="flex gap-2">
        <PencilButton onClick={onClose} className="flex-1 justify-center">Cancelar</PencilButton>
        <button onClick={handle} disabled={loading}
          className="flex-1 justify-center inline-flex items-center gap-1.5 px-4 py-2 rounded-xl font-hand font-bold text-sm bg-red-700 text-white border-2 border-red-900 shadow-[2px_2px_0px_#7f1d1d] cursor-pointer disabled:opacity-50">
          <Trash2 className="w-4 h-4" />{loading ? 'Eliminando…' : 'Sí, eliminar'}
        </button>
      </div>
    </Modal>
  );
}

// ── Sección Usuarios ──────────────────────────────────────────────────────────

function UserModal({ user, onClose, onSaved }: { user: UserRecord | null; onClose: () => void; onSaved: () => void }) {
  const isEdit = !!user;
  const [name, setName] = useState(user?.name ?? '');
  const [email, setEmail] = useState(user?.email ?? '');
  const [password, setPassword] = useState('');
  const [isAdmin, setIsAdmin] = useState(user?.is_admin ?? false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault(); setError(''); setLoading(true);
    try {
      if (isEdit) await usersApi.update(user._id, { name, email, is_admin: isAdmin });
      else {
        if (!password) { setError('La contraseña es obligatoria al crear un usuario.'); setLoading(false); return; }
        await usersApi.create({ name, email, password, is_admin: isAdmin } as CreateUserParams);
      }
      onSaved();
    } catch (err: any) { setError(err?.response?.data?.error || 'Error al guardar el usuario.'); }
    finally { setLoading(false); }
  };

  return (
    <Modal open onClose={onClose} title={isEdit ? 'Editar usuario' : 'Crear usuario'}>
      <form onSubmit={handleSubmit} className="flex flex-col gap-3">
        <div><label className={labelCls}>NOMBRE</label><input value={name} onChange={e => setName(e.target.value)} required placeholder="Nombre completo" className={inputCls} /></div>
        <div><label className={labelCls}>EMAIL</label><input type="email" value={email} onChange={e => setEmail(e.target.value)} required placeholder="correo@ejemplo.com" className={inputCls} /></div>
        {!isEdit && <div><label className={labelCls}>CONTRASEÑA</label><input type="password" value={password} onChange={e => setPassword(e.target.value)} placeholder="Mínimo 6 caracteres" className={inputCls} /></div>}
        <label className="flex items-center gap-2.5 cursor-pointer select-none">
          <input type="checkbox" checked={isAdmin} onChange={e => setIsAdmin(e.target.checked)} className="w-4 h-4 accent-stone-700" />
          <span className="text-stone-700 text-sm font-hand">Rol de Administrador</span>
        </label>
        {error && <ErrBox msg={error} />}
        <div className="flex gap-2 mt-1">
          <PencilButton type="button" onClick={onClose} className="flex-1 justify-center">Cancelar</PencilButton>
          <PencilButton type="submit" variant="solid" disabled={loading} className="flex-1 justify-center">{loading ? 'Guardando…' : isEdit ? 'Guardar' : 'Crear'}</PencilButton>
        </div>
      </form>
    </Modal>
  );
}

function ResetPasswordModal({ user, onClose }: { user: UserRecord; onClose: () => void }) {
  const [password, setPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [done, setDone] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (password !== confirm) { setError('Las contraseñas no coinciden.'); return; }
    setError(''); setLoading(true);
    try { await usersApi.resetPassword(user._id, password); setDone(true); }
    catch (err: any) { setError(err?.response?.data?.error || 'Error al restablecer.'); }
    finally { setLoading(false); }
  };

  return (
    <Modal open onClose={onClose} title="Restablecer contraseña" maxWidth="max-w-sm">
      <p className="text-stone-500 text-[13px] font-hand mb-4">{user.name} — {user.email}</p>
      {done ? (
        <div className="text-center py-4">
          <div className="text-emerald-600 text-3xl mb-2">✓</div>
          <p className="text-stone-600 text-sm font-hand">Contraseña restablecida correctamente.</p>
          <div className="flex justify-center mt-3"><PencilButton onClick={onClose}>Cerrar</PencilButton></div>
        </div>
      ) : (
        <form onSubmit={handleSubmit} className="flex flex-col gap-3">
          <div><label className={labelCls}>NUEVA CONTRASEÑA</label><input type="password" value={password} onChange={e => setPassword(e.target.value)} required placeholder="Mínimo 6 caracteres" className={inputCls} /></div>
          <div><label className={labelCls}>CONFIRMAR</label><input type="password" value={confirm} onChange={e => setConfirm(e.target.value)} required className={inputCls} /></div>
          {error && <ErrBox msg={error} />}
          <div className="flex gap-2 mt-1">
            <PencilButton type="button" onClick={onClose} className="flex-1 justify-center">Cancelar</PencilButton>
            <PencilButton type="submit" variant="solid" disabled={loading} className="flex-1 justify-center">{loading ? 'Guardando…' : 'Restablecer'}</PencilButton>
          </div>
        </form>
      )}
    </Modal>
  );
}

type UserModalState =
  | { type: 'none' }
  | { type: 'create' }
  | { type: 'edit'; user: UserRecord }
  | { type: 'reset'; user: UserRecord }
  | { type: 'delete'; user: UserRecord };

function UsersSection({ authUserId }: { authUserId?: string }) {
  const [users, setUsers] = useState<UserRecord[]>([]);
  const [page, setPage] = useState(1);
  const [hasNext, setHasNext] = useState(false);
  const [search, setSearch] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [modal, setModal] = useState<UserModalState>({ type: 'none' });

  const fetchUsers = useCallback(async (p: number, q: string) => {
    setLoading(true); setError('');
    try {
      const res = await usersApi.list({ page: p, search: q || undefined, per_page: 15 });
      setUsers(res.data.results); setHasNext(res.data.has_next); setPage(p);
    } catch (e: any) {
      setError(e?.response?.data?.error || 'Error al cargar usuarios.');
    } finally { setLoading(false); }
  }, []);

  useEffect(() => { fetchUsers(1, ''); }, [fetchUsers]);

  const closeModal = () => setModal({ type: 'none' });
  const onSaved   = () => { closeModal(); fetchUsers(page, search); };
  const onDeleted = () => { closeModal(); fetchUsers(1, search); };

  return (
    <>
      <div className="flex gap-2.5 mb-4 flex-wrap">
        <input value={search}
          onChange={e => { setSearch(e.target.value); fetchUsers(1, e.target.value); }}
          placeholder="Buscar por nombre o email…"
          className="flex-1 min-w-[200px] bg-[#faf6ee] border-2 border-[#3f3429] rounded-xl px-3.5 py-2 text-sm font-hand outline-none" />
        <PencilButton variant="solid" onClick={() => setModal({ type: 'create' })} icon={<UserPlus className="w-4 h-4" />}>Nuevo usuario</PencilButton>
      </div>

      {error && <div className="mb-3 flex gap-2 items-center"><ErrBox msg={error} /><PencilButton onClick={() => fetchUsers(page, search)} icon={<RefreshCw className="w-4 h-4" />}>Reintentar</PencilButton></div>}

      <div className="bg-[#faf6ee] border-2 border-[#2b251d] rounded-2xl overflow-hidden shadow-[3px_3.5px_0_rgba(43,37,29,0.1)]">
        <div className="overflow-x-auto scrollbar-none">
        <table className="w-full border-collapse min-w-[600px]">
          <thead><tr className="bg-[#efe7d6]">{['Nombre', 'Email', 'Rol', 'Creado', 'Acciones'].map(h => <th key={h} className={th}>{h}</th>)}</tr></thead>
          <tbody>
            {loading && <tr><td colSpan={5} className="p-8 text-center text-stone-500 font-hand">Cargando…</td></tr>}
            {!loading && !error && users.length === 0 && <tr><td colSpan={5} className="p-8 text-center text-stone-500 font-hand">No se encontraron usuarios.</td></tr>}
            {!loading && users.map(u => {
              const isSelf = u._id === authUserId;
              return (
                <tr key={u._id} className="border-t border-stone-800/10 hover:bg-[#f0e9da] transition-colors">
                  <td className={`${td} text-stone-800`}>{u.name}{isSelf && <span className="ml-1.5 text-indigo-600 text-[11px] font-bold">(tú)</span>}</td>
                  <td className={`${td} text-stone-500 font-mono text-xs`}>{u.email}</td>
                  <td className={td}><Tag tone={u.is_admin ? 'blue' : 'neutral'}>{u.is_admin ? 'Admin' : 'Usuario'}</Tag></td>
                  <td className={`${td} text-stone-500 text-xs`}>{formatDate(u.created_at)}</td>
                  <td className={td}>
                    <div className="flex gap-1.5">
                      <button onClick={() => setModal({ type: 'edit', user: u })} title="Editar" className={`${iconBtn} border-stone-300 text-stone-600 hover:bg-stone-100`}><Pencil className="w-4 h-4" /></button>
                      <button onClick={() => setModal({ type: 'reset', user: u })} title="Restablecer contraseña" className={`${iconBtn} border-amber-300 text-amber-700 hover:bg-amber-50`}><KeyRound className="w-4 h-4" /></button>
                      {!isSelf && <button onClick={() => setModal({ type: 'delete', user: u })} title="Eliminar" className={`${iconBtn} border-red-300 text-red-700 hover:bg-red-50`}><Trash2 className="w-4 h-4" /></button>}
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
        </div>
      </div>

      {(page > 1 || hasNext) && (
        <div className="flex justify-center gap-3 mt-4 items-center font-hand">
          <PencilButton disabled={page <= 1} onClick={() => fetchUsers(page - 1, search)}>← Anterior</PencilButton>
          <span className="text-stone-600 text-sm">Página {page}</span>
          <PencilButton disabled={!hasNext} onClick={() => fetchUsers(page + 1, search)}>Siguiente →</PencilButton>
        </div>
      )}

      {modal.type === 'create' && <UserModal user={null} onClose={closeModal} onSaved={onSaved} />}
      {modal.type === 'edit'   && <UserModal user={modal.user} onClose={closeModal} onSaved={onSaved} />}
      {modal.type === 'reset'  && <ResetPasswordModal user={modal.user} onClose={closeModal} />}
      {modal.type === 'delete' && (
        <DeleteConfirmModal title="Eliminar usuario" name={modal.user.name} onClose={closeModal}
          onConfirm={async () => { await usersApi.delete(modal.user._id); onDeleted(); }} />
      )}
    </>
  );
}

// ── Sección Fármacos ──────────────────────────────────────────────────────────

const DRUG_GROUPS = ['approved', 'investigational', 'experimental', 'withdrawn', 'nutraceutical', 'illicit', 'vet_approved'];
const DRUG_TYPES  = ['small molecule', 'biotech'];

function DrugFormModal({
  initial, title, onClose, onSaved,
}: {
  initial?: DrugSummary;
  title: string;
  onClose: () => void;
  onSaved: () => void;
}) {
  const isEdit = !!initial;
  const [drugbankId,   setDrugbankId]   = useState('');
  const [name,         setName]         = useState(initial?.name ?? '');
  const [type,         setType]         = useState(initial?.type ?? 'small molecule');
  const [groups,       setGroups]       = useState<string[]>(initial?.groups ?? []);
  const [description,  setDescription]  = useState(initial?.description ?? '');
  const [loading,      setLoading]      = useState(false);
  const [error,        setError]        = useState('');

  const toggleGroup = (g: string) =>
    setGroups(prev => prev.includes(g) ? prev.filter(x => x !== g) : [...prev, g]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault(); setError(''); setLoading(true);
    try {
      if (isEdit) {
        const id = (initial!['drugbank-id'] as any) || initial!._id;
        const dbid = typeof id === 'string' ? id : (id?.[0]?.value ?? initial!._id);
        await drugsApi.adminUpdate(dbid, { name, type, groups, description });
      } else {
        if (!drugbankId.trim()) { setError('El DrugBank ID es obligatorio.'); setLoading(false); return; }
        await drugsApi.adminCreate({ name, drugbank_id: drugbankId.trim(), type, groups, description } as DrugCreateParams);
      }
      onSaved();
    } catch (err: any) { setError(err?.response?.data?.error || 'Error al guardar.'); }
    finally { setLoading(false); }
  };

  return (
    <Modal open onClose={onClose} title={title}>
      <form onSubmit={handleSubmit} className="flex flex-col gap-3">
        {!isEdit && (
          <div>
            <label className={labelCls}>DRUGBANK ID <span className="text-red-500">*</span></label>
            <input value={drugbankId} onChange={e => setDrugbankId(e.target.value)} required
              placeholder="DB00001" className={inputCls} />
            <p className="text-[11px] text-stone-500 mt-0.5 font-mono">Formato: DB##### — debe ser único</p>
          </div>
        )}
        <div>
          <label className={labelCls}>NOMBRE <span className="text-red-500">*</span></label>
          <input value={name} onChange={e => setName(e.target.value)} required className={inputCls} />
        </div>
        <div>
          <label className={labelCls}>TIPO</label>
          <select value={type} onChange={e => setType(e.target.value)} className={inputCls}>
            {DRUG_TYPES.map(t => <option key={t} value={t}>{t}</option>)}
          </select>
        </div>
        <div>
          <label className={labelCls}>GRUPOS</label>
          <div className="flex flex-wrap gap-2 mt-1">
            {DRUG_GROUPS.map(g => (
              <label key={g} className="flex items-center gap-1.5 cursor-pointer select-none">
                <input type="checkbox" checked={groups.includes(g)} onChange={() => toggleGroup(g)} className="w-3.5 h-3.5 accent-stone-700" />
                <span className="text-stone-700 text-xs font-mono">{g}</span>
              </label>
            ))}
          </div>
        </div>
        <div>
          <label className={labelCls}>DESCRIPCIÓN</label>
          <textarea value={description} onChange={e => setDescription(e.target.value)} rows={3} className={`${inputCls} resize-y`} />
        </div>
        {error && <ErrBox msg={error} />}
        <div className="flex gap-2 mt-1">
          <PencilButton type="button" onClick={onClose} className="flex-1 justify-center">Cancelar</PencilButton>
          <PencilButton type="submit" variant="solid" disabled={loading} className="flex-1 justify-center">
            {loading ? 'Guardando…' : isEdit ? 'Guardar cambios' : 'Crear fármaco'}
          </PencilButton>
        </div>
      </form>
    </Modal>
  );
}

type DrugModal = { type: 'none' } | { type: 'create' } | { type: 'edit'; drug: DrugSummary } | { type: 'delete'; drug: DrugSummary };

function DrugsSection() {
  const [drugs,   setDrugs]   = useState<DrugSummary[]>([]);
  const [page,    setPage]    = useState(1);
  const [hasNext, setHasNext] = useState(false);
  const [search,  setSearch]  = useState('');
  const [loading, setLoading] = useState(true);
  const [error,   setError]   = useState('');
  const [modal,   setModal]   = useState<DrugModal>({ type: 'none' });

  const fetchDrugs = useCallback(async (p: number, q: string) => {
    setLoading(true); setError('');
    try {
      const res = await drugsApi.list({ search: q || undefined, page: p });
      setDrugs(res.data.results); setHasNext(res.data.has_next); setPage(p);
    } catch (e: any) {
      setError(e?.response?.data?.error || 'Error al cargar fármacos.');
    } finally { setLoading(false); }
  }, []);

  useEffect(() => { fetchDrugs(1, ''); }, [fetchDrugs]);

  const closeModal = () => setModal({ type: 'none' });
  const onSaved   = () => { closeModal(); fetchDrugs(page, search); };
  const onDeleted = () => { closeModal(); fetchDrugs(1, search); };

  const drugId = (d: DrugSummary): string => {
    const raw = d['drugbank-id'];
    if (typeof raw === 'string') return raw;
    if (Array.isArray(raw)) return (raw[0] as any)?.value ?? d._id;
    return d._id;
  };

  const groupTone = (g: string): 'green' | 'amber' | 'orange' | 'neutral' =>
    g === 'approved' ? 'green' : g === 'withdrawn' ? 'amber' : (g.includes('invest') || g === 'experimental') ? 'orange' : 'neutral';

  return (
    <>
      <div className="flex gap-2.5 mb-4 flex-wrap">
        <input value={search}
          onChange={e => { setSearch(e.target.value); fetchDrugs(1, e.target.value); }}
          placeholder="Buscar fármaco por nombre o ID…"
          className="flex-1 min-w-[200px] bg-[#faf6ee] border-2 border-[#3f3429] rounded-xl px-3.5 py-2 text-sm font-hand outline-none" />
        <PencilButton variant="solid" onClick={() => setModal({ type: 'create' })} icon={<Plus className="w-4 h-4" />}>Nuevo fármaco</PencilButton>
      </div>

      {error && <div className="mb-3 flex gap-2 items-center flex-wrap"><ErrBox msg={error} /><PencilButton onClick={() => fetchDrugs(page, search)} icon={<RefreshCw className="w-4 h-4" />}>Reintentar</PencilButton></div>}

      <div className="bg-[#faf6ee] border-2 border-[#2b251d] rounded-2xl overflow-hidden shadow-[3px_3.5px_0_rgba(43,37,29,0.1)]">
        <div className="overflow-x-auto scrollbar-none">
        <table className="w-full border-collapse min-w-[580px]">
          <thead><tr className="bg-[#efe7d6]">{['Nombre', 'DrugBank ID', 'Tipo', 'Grupos', 'Acciones'].map(h => <th key={h} className={th}>{h}</th>)}</tr></thead>
          <tbody>
            {loading && <tr><td colSpan={5} className="p-8 text-center text-stone-500 font-hand">Cargando…</td></tr>}
            {!loading && !error && drugs.length === 0 && <tr><td colSpan={5} className="p-8 text-center text-stone-500 font-hand">No se encontraron fármacos.</td></tr>}
            {!loading && drugs.map(d => (
              <tr key={d._id} className="border-t border-stone-800/10 hover:bg-[#f0e9da] transition-colors">
                <td className={`${td} text-stone-800 font-medium max-w-[220px] truncate`}>{d.name}</td>
                <td className={`${td} text-sky-700 font-mono text-xs`}>{drugId(d)}</td>
                <td className={`${td} text-stone-500 text-xs`}>{d.type || '—'}</td>
                <td className={td}>
                  <div className="flex gap-1 flex-wrap">
                    {(d.groups ?? []).map(g => <Tag key={g} tone={groupTone(g)}>{g}</Tag>)}
                  </div>
                </td>
                <td className={td}>
                  <div className="flex gap-1.5">
                    <button onClick={() => setModal({ type: 'edit', drug: d })} title="Editar" className={`${iconBtn} border-stone-300 text-stone-600 hover:bg-stone-100`}><Pencil className="w-4 h-4" /></button>
                    <button onClick={() => setModal({ type: 'delete', drug: d })} title="Eliminar" className={`${iconBtn} border-red-300 text-red-700 hover:bg-red-50`}><Trash2 className="w-4 h-4" /></button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        </div>
      </div>

      {(page > 1 || hasNext) && (
        <div className="flex justify-center gap-3 mt-4 items-center font-hand">
          <PencilButton disabled={page <= 1} onClick={() => fetchDrugs(page - 1, search)}>← Anterior</PencilButton>
          <span className="text-stone-600 text-sm">Página {page}</span>
          <PencilButton disabled={!hasNext} onClick={() => fetchDrugs(page + 1, search)}>Siguiente →</PencilButton>
        </div>
      )}

      {modal.type === 'create' && <DrugFormModal title="Nuevo fármaco" onClose={closeModal} onSaved={onSaved} />}
      {modal.type === 'edit'   && <DrugFormModal title="Editar fármaco" initial={modal.drug} onClose={closeModal} onSaved={onSaved} />}
      {modal.type === 'delete' && (
        <DeleteConfirmModal title="Eliminar fármaco" name={modal.drug.name} onClose={closeModal}
          onConfirm={async () => { await drugsApi.adminDelete(drugId(modal.drug)); onDeleted(); }} />
      )}
    </>
  );
}

// ── Sección Dianas ────────────────────────────────────────────────────────────

function TargetFormModal({
  initial, title, onClose, onSaved,
}: {
  initial?: TargetRecord;
  title: string;
  onClose: () => void;
  onSaved: () => void;
}) {
  const isEdit = !!initial;
  const [targetId,         setTargetId]         = useState('');
  const [name,             setName]             = useState(initial?.name ?? '');
  const [geneName,         setGeneName]         = useState(initial?.gene_name ?? '');
  const [organism,         setOrganism]         = useState(initial?.organism ?? '');
  const [uniprotId,        setUniprotId]        = useState((initial as any)?.uniprot_id ?? '');
  const [cellularLocation, setCellularLocation] = useState(initial?.cellular_location ?? '');
  const [knownAction,      setKnownAction]      = useState(initial?.known_action ?? '');
  const [loading,          setLoading]          = useState(false);
  const [error,            setError]            = useState('');

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault(); setError(''); setLoading(true);
    try {
      const data = { name, gene_name: geneName, organism, cellular_location: cellularLocation, known_action: knownAction };
      if (isEdit) {
        await targetsApi.adminUpdate(initial!.id, data as TargetAdminUpdate);
      } else {
        if (!targetId.trim()) { setError('El ID de diana es obligatorio.'); setLoading(false); return; }
        await targetsApi.adminCreate({ ...data, drugbank_target_id: targetId.trim(), uniprot_id: uniprotId } as TargetCreateParams);
      }
      onSaved();
    } catch (err: any) { setError(err?.response?.data?.error || 'Error al guardar.'); }
    finally { setLoading(false); }
  };

  return (
    <Modal open onClose={onClose} title={title}>
      <form onSubmit={handleSubmit} className="flex flex-col gap-3">
        {!isEdit && (
          <div>
            <label className={labelCls}>ID DE DIANA <span className="text-red-500">*</span></label>
            <input value={targetId} onChange={e => setTargetId(e.target.value)} required
              placeholder="BE0000001" className={inputCls} />
            <p className="text-[11px] text-stone-500 mt-0.5 font-mono">Formato: BE####### — debe ser único</p>
          </div>
        )}
        <div>
          <label className={labelCls}>NOMBRE <span className="text-red-500">*</span></label>
          <input value={name} onChange={e => setName(e.target.value)} required className={inputCls} />
        </div>
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className={labelCls}>GEN</label>
            <input value={geneName} onChange={e => setGeneName(e.target.value)} placeholder="p.ej. EGFR" className={inputCls} />
          </div>
          <div>
            <label className={labelCls}>ORGANISMO</label>
            <input value={organism} onChange={e => setOrganism(e.target.value)} placeholder="Humans" className={inputCls} />
          </div>
        </div>
        {!isEdit && (
          <div>
            <label className={labelCls}>UNIPROT ID</label>
            <input value={uniprotId} onChange={e => setUniprotId(e.target.value)} placeholder="P00533" className={inputCls} />
          </div>
        )}
        <div>
          <label className={labelCls}>LOCALIZACIÓN CELULAR</label>
          <input value={cellularLocation} onChange={e => setCellularLocation(e.target.value)} className={inputCls} />
        </div>
        <div>
          <label className={labelCls}>ACCIÓN CONOCIDA</label>
          <select value={knownAction} onChange={e => setKnownAction(e.target.value)} className={inputCls}>
            <option value="">— sin especificar —</option>
            <option value="yes">Sí</option>
            <option value="no">No</option>
            <option value="unknown">Desconocida</option>
          </select>
        </div>
        {error && <ErrBox msg={error} />}
        <div className="flex gap-2 mt-1">
          <PencilButton type="button" onClick={onClose} className="flex-1 justify-center">Cancelar</PencilButton>
          <PencilButton type="submit" variant="solid" disabled={loading} className="flex-1 justify-center">
            {loading ? 'Guardando…' : isEdit ? 'Guardar cambios' : 'Crear diana'}
          </PencilButton>
        </div>
      </form>
    </Modal>
  );
}

type TargetModal = { type: 'none' } | { type: 'create' } | { type: 'edit'; target: TargetRecord } | { type: 'delete'; target: TargetRecord };

function TargetsSection() {
  const [targets, setTargets] = useState<TargetRecord[]>([]);
  const [page,    setPage]    = useState(1);
  const [hasNext, setHasNext] = useState(false);
  const [search,  setSearch]  = useState('');
  const [loading, setLoading] = useState(true);
  const [error,   setError]   = useState('');
  const [modal,   setModal]   = useState<TargetModal>({ type: 'none' });

  const fetchTargets = useCallback(async (p: number, q: string) => {
    setLoading(true); setError('');
    try {
      const res = await targetsApi.list({ search: q || undefined, page: p, per_page: 15 });
      setTargets(res.data.results); setHasNext(res.data.has_next); setPage(p);
    } catch (e: any) {
      setError(e?.response?.data?.error || 'Error al cargar dianas.');
    } finally { setLoading(false); }
  }, []);

  useEffect(() => { fetchTargets(1, ''); }, [fetchTargets]);

  const closeModal = () => setModal({ type: 'none' });
  const onSaved   = () => { closeModal(); fetchTargets(page, search); };
  const onDeleted = () => { closeModal(); fetchTargets(1, search); };

  return (
    <>
      <div className="flex gap-2.5 mb-4 flex-wrap">
        <input value={search}
          onChange={e => { setSearch(e.target.value); fetchTargets(1, e.target.value); }}
          placeholder="Buscar diana por nombre o gen…"
          className="flex-1 min-w-[200px] bg-[#faf6ee] border-2 border-[#3f3429] rounded-xl px-3.5 py-2 text-sm font-hand outline-none" />
        <PencilButton variant="solid" onClick={() => setModal({ type: 'create' })} icon={<Plus className="w-4 h-4" />}>Nueva diana</PencilButton>
      </div>

      {error && <div className="mb-3 flex gap-2 items-center flex-wrap"><ErrBox msg={error} /><PencilButton onClick={() => fetchTargets(page, search)} icon={<RefreshCw className="w-4 h-4" />}>Reintentar</PencilButton></div>}

      <div className="bg-[#faf6ee] border-2 border-[#2b251d] rounded-2xl overflow-hidden shadow-[3px_3.5px_0_rgba(43,37,29,0.1)]">
        <div className="overflow-x-auto scrollbar-none">
        <table className="w-full border-collapse min-w-[640px]">
          <thead><tr className="bg-[#efe7d6]">{['Nombre', 'Gen', 'UniProt', 'Organismo', 'Fármacos', 'Acciones'].map(h => <th key={h} className={th}>{h}</th>)}</tr></thead>
          <tbody>
            {loading && <tr><td colSpan={6} className="p-8 text-center text-stone-500 font-hand">Cargando…</td></tr>}
            {!loading && !error && targets.length === 0 && <tr><td colSpan={6} className="p-8 text-center text-stone-500 font-hand">No se encontraron dianas.</td></tr>}
            {!loading && targets.map(t => (
              <tr key={t.id} className="border-t border-stone-800/10 hover:bg-[#f0e9da] transition-colors">
                <td className={`${td} text-stone-800 font-medium max-w-[200px] truncate`}>{t.name}</td>
                <td className={`${td} text-sky-700 font-mono text-xs`}>{t.gene_name || '—'}</td>
                <td className={`${td} text-purple-700 font-mono text-xs`}>{t.uniprot_id || '—'}</td>
                <td className={`${td} text-stone-500 text-xs`}>{t.organism || '—'}</td>
                <td className={`${td} text-stone-600 text-center`}>{t.drug_count}</td>
                <td className={td}>
                  <div className="flex gap-1.5">
                    <button onClick={() => setModal({ type: 'edit', target: t })} title="Editar" className={`${iconBtn} border-stone-300 text-stone-600 hover:bg-stone-100`}><Pencil className="w-4 h-4" /></button>
                    <button onClick={() => setModal({ type: 'delete', target: t })} title="Eliminar" className={`${iconBtn} border-red-300 text-red-700 hover:bg-red-50`}><Trash2 className="w-4 h-4" /></button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        </div>
      </div>

      {(page > 1 || hasNext) && (
        <div className="flex justify-center gap-3 mt-4 items-center font-hand">
          <PencilButton disabled={page <= 1} onClick={() => fetchTargets(page - 1, search)}>← Anterior</PencilButton>
          <span className="text-stone-600 text-sm">Página {page}</span>
          <PencilButton disabled={!hasNext} onClick={() => fetchTargets(page + 1, search)}>Siguiente →</PencilButton>
        </div>
      )}

      {modal.type === 'create' && <TargetFormModal title="Nueva diana" onClose={closeModal} onSaved={onSaved} />}
      {modal.type === 'edit'   && <TargetFormModal title="Editar diana" initial={modal.target} onClose={closeModal} onSaved={onSaved} />}
      {modal.type === 'delete' && (
        <DeleteConfirmModal title="Eliminar diana" name={modal.target.name} onClose={closeModal}
          onConfirm={async () => { await targetsApi.adminDelete(modal.target.id); onDeleted(); }} />
      )}
    </>
  );
}

// ── Página principal ──────────────────────────────────────────────────────────

type AdminTab = 'users' | 'drugs' | 'targets';

const TABS: { key: AdminTab; label: string; Icon: any }[] = [
  { key: 'users',   label: 'Usuarios',  Icon: UserPlus },
  { key: 'drugs',   label: 'Fármacos',  Icon: Pill },
  { key: 'targets', label: 'Dianas',    Icon: Crosshair },
];

export default function AdminPage() {
  const { user: authUser } = useAuth();
  usePageTitle('Administración');
  const [tab, setTab] = useState<AdminTab>('users');

  return (
    <NotebookLayout navbar={<NotebookNavbar />} maxWidth="max-w-6xl">
      <div className="mb-5">
        <HandTitle className="text-3xl flex items-center gap-2"><Settings className="w-7 h-7 text-amber-800" /> Administración</HandTitle>
        <p className="text-sm text-stone-500 font-hand mt-1">Gestión de usuarios, fármacos y dianas. Solo administradores acceden aquí.</p>
      </div>

      <div className="flex gap-2 border-b border-stone-800/10 pb-3 mb-6 overflow-x-auto scrollbar-none">
        {TABS.map(({ key, label, Icon }) => (
          <button key={key} onClick={() => setTab(key)}
            className={`px-3 sm:px-4 py-2 sm:py-2.5 rounded-xl font-hand text-sm sm:text-base font-bold flex items-center gap-1.5 sm:gap-2 border-2 cursor-pointer transition-all shrink-0 whitespace-nowrap ${
              tab === key
                ? 'bg-[#2d2621] text-[#faf6ee] border-[#1e1814] shadow-[2px_2px_0px_#1e1814]'
                : 'bg-white text-stone-700 border-stone-300 hover:bg-stone-50'
            }`}>
            <Icon className="w-4 h-4 sm:w-5 sm:h-5" /> {label}
          </button>
        ))}
      </div>

      {tab === 'users'   && <UsersSection authUserId={authUser?._id} />}
      {tab === 'drugs'   && <DrugsSection />}
      {tab === 'targets' && <TargetsSection />}
    </NotebookLayout>
  );
}
