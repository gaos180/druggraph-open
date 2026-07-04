# 01 — Primeros Pasos

## Requisitos Previos

- Navegador moderno (Chrome 90+, Firefox 88+, Edge 90+)
- El stack de DrugGraph levantado localmente (ver [README de despliegue](../arc42/07_deployment_view.md))
- Acceso a `http://localhost:3000`

---

## Registro de cuenta

1. Abre `http://localhost:3000` en el navegador.
2. Serás redirigido a la pantalla de **Login**.
3. Haz clic en "¿No tienes cuenta? Regístrate".
4. Completa el formulario:
   - **Email**: dirección de correo válida (será tu identificador de acceso)
   - **Nombre**: nombre de usuario visible
   - **Contraseña**: mínimo 6 caracteres
5. Haz clic en **Registrarse**.
6. Si el registro es exitoso, serás redirigido automáticamente al Dashboard.

> **Cuenta de administrador predefinida** (solo para desarrollo):  
> Email: `admin@druggraph.dev` | Contraseña: `admin1234`  
> Crea con `python seed_admin.py` la primera vez.

---

## Inicio de Sesión

1. Ingresa tu email y contraseña en la pantalla de Login.
2. Haz clic en **Iniciar Sesión**.
3. El token JWT se almacena en el navegador y se incluye automáticamente en todas las requests subsiguientes.
4. La sesión persiste mientras el token sea válido (no expira en la configuración por defecto).

> Si ves el error "Token inválido o expirado", cierra sesión (`/logout` desde el menú) y vuelve a ingresar.

---

## Dashboard

Tras el login aterrizas en el **Dashboard** (`/dashboard`), que presenta accesos directos a todas las funcionalidades:

| Tarjeta | Ruta | Descripción |
|---------|------|-------------|
| Análisis de Red | `/network` | Topología global de la red de interacciones |
| Base de Datos | `/drugs` | Explorar y buscar fármacos |
| Laboratorio Virtual | `/sandbox` | Comparar compuestos virtuales |
| Búsqueda BLAST | `/blast` | Buscar dianas por homología de secuencia |
| Herramientas | `/tools` | Análisis DEG, Reposicionamiento y Toxicidad |

La barra de navegación superior incluye acceso directo a **🔧 Herramientas** desde cualquier página.

---

## Cerrar Sesión

Haz clic en el botón de logout en la barra de navegación (o navega directamente a `/login`). El token se elimina de `localStorage` y se redirige al login.
