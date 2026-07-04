import { useState, useEffect, useCallback } from 'react';
import { drugsApi, DrugsResponse, FiltersResponse } from '../api/drugs';

export function useDrugs() {
  const [data, setData] = useState<DrugsResponse | null>(null);
  const [filters, setFilters] = useState<FiltersResponse>({ types: [], groups: [] });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  // Texto en pantalla (no dispara la API al escribir)
  const [searchInput, setSearchInput] = useState('');

  // Query comprometida (esta sí dispara la API)
  const [query, setQuery] = useState({
    search: '',
    type: '',
    group: '',
    page: 1,
  });

  // Cargar filtros una sola vez al montar el componente
  useEffect(() => {
    drugsApi.filters()
      .then(res => setFilters(res.data))
      .catch(() => {});
  }, []);

  const fetchDrugs = useCallback(() => {
    setLoading(true);
    setError('');

    // Eliminamos el bloqueo restrictivo para permitir listar por defecto o por filtros puros
    drugsApi.list({
      search: query.search || undefined, // Envía undefined si está vacío para activar comportamiento por defecto del backend
      drug_type: query.type || undefined,
      group: query.group || undefined,
      page: query.page,
    })
      .then(res => setData(res.data))
      .catch(() => setError('Error al cargar fármacos. ¿Está corriendo el servidor backend?'))
      .finally(() => setLoading(false));
  }, [query]);

  useEffect(() => {
    fetchDrugs();
  }, [fetchDrugs]);

  // Solo actualiza el input visual
  const updateSearch = (text: string) => setSearchInput(text);

  // Confirma la búsqueda al dar Enter o Submit
  const triggerSearch = () => {
    setQuery(q => ({ ...q, search: searchInput.trim(), page: 1 }));
  };

  const updateType = (type: string) =>
    setQuery(q => ({ ...q, type, page: 1 }));

  const updateGroup = (group: string) =>
    setQuery(q => ({ ...q, group, page: 1 }));

  const goToPage = (page: number) =>
    setQuery(q => ({ ...q, page }));

  const nextPage = () => {
    if (data?.has_next) goToPage(query.page + 1);
  };

  const prevPage = () => {
    if (data?.has_prev) goToPage(query.page - 1);
  };

  return {
    data,
    filters,
    loading,
    error,
    searchInput,
    query,
    updateSearch,
    triggerSearch,
    updateType,
    updateGroup,
    goToPage,
    nextPage,
    prevPage,
  };
}