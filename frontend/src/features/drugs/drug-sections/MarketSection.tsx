import React from 'react';
import type { DrugRecord } from '../../../types/drug';

export default function MarketSection({ drug }: { drug: DrugRecord }) {
  if (!drug) return <p style={{ color: '#78716c', fontStyle: 'italic' }}>Cargando datos de mercado...</p>;

  // 1. Normalización segura de PRICES (Precios)
  // DrugBank a veces anida: drug.prices = [ ... ] o drug.prices = { price: [ ... ] }
  let rawPrices: any[] = [];
  if (drug.prices) {
    if (Array.isArray(drug.prices)) {
      rawPrices = drug.prices;
    } else if (drug.prices.price && Array.isArray(drug.prices.price)) {
      rawPrices = drug.prices.price;
    } else if (drug.prices.price) {
      rawPrices = [drug.prices.price];
    }
  }

  // 2. Normalización segura de PRODUCTS (Catálogo comercial)
  // DrugBank a veces anida: drug.products = [ ... ] o drug.products = { product: [ ... ] }
  let rawProducts: any[] = [];
  if (drug.products) {
    if (Array.isArray(drug.products)) {
      rawProducts = drug.products;
    } else if (drug.products.product && Array.isArray(drug.products.product)) {
      rawProducts = drug.products.product;
    } else if (drug.products.product) {
      rawProducts = [drug.products.product];
    }
  }

  // 3. Normalización segura de PACKAGERS (Distribuidores/Empacadores)
  let rawPackagers: any[] = [];
  if (drug.packagers) {
    if (Array.isArray(drug.packagers)) {
      rawPackagers = drug.packagers;
    } else if (drug.packagers.packager && Array.isArray(drug.packagers.packager)) {
      rawPackagers = drug.packagers.packager;
    } else if (drug.packagers.packager) {
      rawPackagers = [drug.packagers.packager];
    }
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      
      {/* SECCIÓN A: PRECIOS */}
      <div className="detail-section">
        <label style={{ fontSize: '1.1rem', color: '#065f46', display: 'block', marginBottom: '10px' }}>
          💰 Costos de Adquisición e Importación ({rawPrices.length})
        </label>
        
        {rawPrices.length > 0 ? (
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))', gap: '14px' }}>
            {rawPrices.map((p: any, i: number) => {
              // Extraer costo de forma segura (soportando objetos o strings)
              const costValue = p.cost?.value || p.cost?.['#text'] || (typeof p.cost === 'string' ? p.cost : 'N/A');
              const costCurrency = p.cost?.currency || 'USD';
              const description = p.description || p.format || 'Presentación Comercial Indexada';

              return (
                <div key={i} style={{ background: '#f3ece0', padding: '16px', borderRadius: '8px', borderLeft: '4px solid #10b981', display: 'flex', justifyContent: 'space-between', alignItems: 'center', border: '1px solid #d6ccbb' }}>
                  <div>
                    <strong style={{ color: '#1c1917', fontSize: '0.95rem' }}>{description}</strong>
                    <p style={{ margin: '4px 0 0 0', fontSize: '0.8rem', color: '#78716c' }}>
                      Unidad Mínima: <span style={{ color: '#44403c' }}>{p.unit || 'N/A'}</span>
                    </p>
                  </div>
                  <div style={{ fontSize: '1.25rem', color: '#065f46', fontWeight: 'bold', fontFamily: 'monospace', marginLeft: '10px' }}>
                    {costValue !== 'N/A' ? `${costValue} ${costCurrency}` : 'Consultar'}
                  </div>
                </div>
              );
            })}
          </div>
        ) : (
          <div style={{ background: '#f3ece0', padding: '16px', borderRadius: '8px', color: '#57534e', fontStyle: 'italic', fontSize: '0.9rem' }}>
            💡 No hay registros de precios crudos en `drug.prices` para este documento.
          </div>
        )}
      </div>

      {/* SECCIÓN B: PRODUCTOS COMERCIALES */}
      <div className="detail-section">
        <label style={{ fontSize: '1.1rem', color: '#6b21a8', display: 'block', marginBottom: '10px' }}>
          🏢 Catálogo de Marcas y Laboratorios Registrados ({rawProducts.length})
        </label>

        {rawProducts.length > 0 ? (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', maxHeight: '450px', overflowY: 'auto', paddingRight: '6px' }}>
            {rawProducts.map((prod: any, i: number) => {
              // Manejo de campos con guiones del XML original mapeado a JSON
              const dosage = prod['dosage-form'] || prod.dosageForm || 'N/A';
              const strength = prod.strength || 'N/A';
              const labeller = prod.labeller || prod.company || 'Laboratorio Desconocido';
              const country = prod.country || 'Internacional';
              const isGeneric = String(prod.generic) === 'true';
              const isOtc = String(prod['over-the-counter']) === 'true' || String(prod.overTheCounter) === 'true';

              return (
                <div key={i} style={{ background: '#f3ece0', padding: '14px', borderRadius: '8px', display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', border: '1px solid #d6ccbb', gap: '15px' }}>
                  <div>
                    <strong style={{ color: '#1c1917', fontSize: '1.05rem' }}>{prod.name || 'Fármaco genérico'}</strong> 
                    <span style={{ fontSize: '0.85rem', color: '#57534e', marginLeft: '8px' }}>({strength})</span>
                    
                    <p style={{ margin: '6px 0 0 0', fontSize: '0.88rem', color: '#44403c' }}>
                      🏭 Fabricante: <strong style={{ color: '#1e40af' }}>{labeller}</strong> | Vía: {prod.route || 'N/A'}
                    </p>
                    <p style={{ margin: '3px 0 0 0', fontSize: '0.8rem', color: '#78716c' }}>
                      Forma: {dosage} | Región: {country} {prod['fda-application-number'] && `| FDA: ${prod['fda-application-number']}`}
                    </p>
                  </div>

                  <div style={{ display: 'flex', flexDirection: 'column', gap: '6px', textAlign: 'right', flexShrink: 0 }}>
                    <span style={{ fontSize: '0.7rem', background: isGeneric ? '#2563eb' : '#db2777', color: '#fff', padding: '3px 8px', borderRadius: '4px', fontWeight: 'bold', textTransform: 'uppercase', letterSpacing: '0.5px' }}>
                      {isGeneric ? 'Genérico' : 'Marca'}
                    </span>
                    <span style={{ fontSize: '0.7rem', background: isOtc ? '#059669' : '#b91c1c', color: '#fff', padding: '3px 8px', borderRadius: '4px', fontWeight: 'bold', textTransform: 'uppercase', letterSpacing: '0.5px' }}>
                      {isOtc ? 'Venta Libre' : 'Receta'}
                    </span>
                  </div>
                </div>
              );
            })}
          </div>
        ) : (
          <div style={{ background: '#f3ece0', padding: '16px', borderRadius: '8px', color: '#57534e', fontStyle: 'italic', fontSize: '0.9rem' }}>
            💡 No se detectaron productos farmacéuticos comerciales en `drug.products` para este sub-registro.
          </div>
        )}
      </div>

      {/* SECCIÓN C: DISTRIBUIDORES / PACKAGERS */}
      {rawPackagers.length > 0 && (
        <div className="detail-section">
          <label style={{ fontSize: '1.1rem', color: '#1e40af', display: 'block', marginBottom: '10px' }}>
            📦 Cadenas de Distribución y Empaque (Packagers)
          </label>
          <div style={{ display: 'flex', gap: '10px', flexWrap: 'wrap' }}>
            {rawPackagers.map((pkg: any, i: number) => (
              <div key={i} style={{ background: '#d6ccbb', padding: '8px 14px', borderRadius: '6px', fontSize: '0.85rem', border: '1px solid #bcae98', color: '#292524' }}>
                🏢 <strong>{pkg.name || pkg}</strong>
              </div>
            ))}
          </div>
        </div>
      )}

    </div>
  );
}