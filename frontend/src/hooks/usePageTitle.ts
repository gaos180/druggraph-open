import { useEffect } from 'react';

export function usePageTitle(pageTitle: string) {
  useEffect(() => {
    if (pageTitle) {
      document.title = `${pageTitle} — DrugGraph`;
    }
  }, [pageTitle]);
}
