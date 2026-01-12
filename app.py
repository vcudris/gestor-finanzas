import streamlit as st
import pandas as pd
import sqlite3
import plotly.express as px
import io
from datetime import datetime

# ==========================================
# 1. BACKEND (Lógica, Base de Datos y Migración)
# ==========================================

def init_db():
    conn = sqlite3.connect('finanzas.db')
    c = conn.cursor()
    
    # 1. Tabla Transacciones (Esquema Base)
    c.execute('''
        CREATE TABLE IF NOT EXISTS transacciones (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fecha TEXT NOT NULL,
            tipo TEXT NOT NULL,
            categoria TEXT NOT NULL,
            monto REAL NOT NULL,
            nota TEXT,
            ubicacion TEXT
        )
    ''')
    
    # 2. Tabla Categorías
    c.execute('''
        CREATE TABLE IF NOT EXISTS categorias (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tipo TEXT NOT NULL,
            nombre TEXT NOT NULL,
            UNIQUE(tipo, nombre)
        )
    ''')

    # 3. Tabla Lugares / Ubicaciones (NUEVA)
    c.execute('''
        CREATE TABLE IF NOT EXISTS lugares (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL UNIQUE
        )
    ''')
    
    # --- MIGRACIÓN AUTOMÁTICA DE ESQUEMA ---
    # Esto evita errores si ya tienes una DB creada sin la columna 'ubicacion'
    try:
        c.execute("SELECT ubicacion FROM transacciones LIMIT 1")
    except sqlite3.OperationalError:
        # Si falla, es porque no existe la columna. La creamos.
        c.execute("ALTER TABLE transacciones ADD COLUMN ubicacion TEXT DEFAULT 'General'")
        conn.commit()
    
    # Datos semilla para Categorías
    c.execute('SELECT count(*) FROM categorias')
    if c.fetchone()[0] == 0:
        defaults = [
            ('Ingreso', 'Salario'), ('Ingreso', 'Inversiones'),
            ('Gasto', 'Alimentación'), ('Gasto', 'Transporte'), ('Gasto', 'Vivienda'),
            ('Gasto', 'Salud'), ('Gasto', 'Ocio'), ('Gasto', 'Servicios')
        ]
        c.executemany('INSERT OR IGNORE INTO categorias (tipo, nombre) VALUES (?,?)', defaults)
    
    # Datos semilla para Lugares
    c.execute('SELECT count(*) FROM lugares')
    if c.fetchone()[0] == 0:
        lugares_defecto = [('Casa',), ('Oficina',), ('Supermercado',), ('Restaurante',), ('Online',)]
        c.executemany('INSERT OR IGNORE INTO lugares (nombre) VALUES (?)', lugares_defecto)

    conn.commit()
    conn.close()

def add_transaction(fecha, tipo, categoria, monto, nota, ubicacion):
    conn = sqlite3.connect('finanzas.db')
    c = conn.cursor()
    c.execute('''
        INSERT INTO transacciones (fecha, tipo, categoria, monto, nota, ubicacion) 
        VALUES (?,?,?,?,?,?)
    ''', (fecha, tipo, categoria, monto, nota, ubicacion))
    conn.commit()
    conn.close()

def delete_transaction(transaccion_id):
    conn = sqlite3.connect('finanzas.db')
    c = conn.cursor()
    c.execute('DELETE FROM transacciones WHERE id = ?', (transaccion_id,))
    conn.commit()
    conn.close()

def get_data():
    conn = sqlite3.connect('finanzas.db')
    try:
        df = pd.read_sql_query("SELECT * FROM transacciones ORDER BY fecha DESC", conn)
        if not df.empty:
            df['fecha'] = pd.to_datetime(df['fecha'])
    except:
        df = pd.DataFrame()
    conn.close()
    return df

# --- Helpers para Listas Desplegables ---

def get_categories(tipo_seleccionado):
    conn = sqlite3.connect('finanzas.db')
    c = conn.cursor()
    c.execute('SELECT nombre FROM categorias WHERE tipo = ? ORDER BY nombre', (tipo_seleccionado,))
    return [row[0] for row in c.fetchall()]

def get_locations():
    conn = sqlite3.connect('finanzas.db')
    c = conn.cursor()
    c.execute('SELECT nombre FROM lugares ORDER BY nombre')
    return [row[0] for row in c.fetchall()]

def add_new_category(tipo, nombre):
    conn = sqlite3.connect('finanzas.db')
    c = conn.cursor()
    try:
        c.execute('INSERT INTO categorias (tipo, nombre) VALUES (?,?)', (tipo, nombre.capitalize()))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()

def add_new_location(nombre):
    conn = sqlite3.connect('finanzas.db')
    c = conn.cursor()
    try:
        c.execute('INSERT INTO lugares (nombre) VALUES (?)', (nombre.capitalize(),))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()

# ==========================================
# 2. FRONTEND (Interfaz de Usuario)
# ==========================================

st.set_page_config(page_title="Gestor Financiero", layout="centered", page_icon="💰")
init_db() # Corre migraciones si es necesario

# --- SIDEBAR (FILTROS) ---
st.sidebar.title("🔍 Filtros")
df_original = get_data()

if not df_original.empty:
    years = sorted(df_original['fecha'].dt.year.unique(), reverse=True)
    current_year = datetime.now().year
    if current_year not in years: years.insert(0, current_year)
    selected_year = st.sidebar.selectbox("Año", years)

    months = {1:"Enero", 2:"Febrero", 3:"Marzo", 4:"Abril", 5:"Mayo", 6:"Junio",
              7:"Julio", 8:"Agosto", 9:"Septiembre", 10:"Octubre", 11:"Noviembre", 12:"Diciembre", 13:"Todos"}
    
    current_month_idx = datetime.now().month - 1
    selected_month_key = st.sidebar.selectbox("Mes", list(months.keys()), format_func=lambda x: months[x], index=current_month_idx)

    if selected_month_key == 13:
        mask = (df_original['fecha'].dt.year == selected_year)
        titulo = f"Año {selected_year}"
    else:
        mask = (df_original['fecha'].dt.year == selected_year) & (df_original['fecha'].dt.month == selected_month_key)
        titulo = f"{months[selected_month_key]} {selected_year}"
    
    df = df_original[mask]
else:
    df = df_original
    titulo = "Histórico"

# --- MAIN ---
st.title(f"💰 Control: {titulo}")
tab1, tab2, tab3 = st.tabs(["📝 Registrar", "📊 Dashboard", "⚙️ Gestión"])

# --- PESTAÑA 1: REGISTRO ---
with tab1:
    st.subheader("Nueva Transacción")
    tipo_global = st.radio("Tipo", ["Gasto", "Ingreso"], horizontal=True, label_visibility="collapsed")

    # FILA 1: Categoría y Lugar (Selectores Inteligentes)
    c_cat, c_loc = st.columns(2)
    
    with c_cat:
        # Lógica Categoría
        col_sel, col_add = st.columns([0.85, 0.15])
        with col_sel:
            cats = get_categories(tipo_global)
            cat_sel = st.selectbox("Categoría", cats)
        with col_add:
            with st.popover("➕"):
                new_cat = st.text_input("Nueva Cat.", key="nk_cat")
                if st.button("Guardar", key="btn_cat"):
                    if new_cat and add_new_category(tipo_global, new_cat):
                        st.success("Ok")
                        st.rerun()

    with c_loc:
        # Lógica Lugar (NUEVO)
        col_l_sel, col_l_add = st.columns([0.85, 0.15])
        with col_l_sel:
            locs = get_locations()
            # Index 0 suele ser 'Casa' o 'General'
            loc_sel = st.selectbox("Lugar / Sede", locs) 
        with col_l_add:
            with st.popover("➕"):
                st.markdown("Nuevo Lugar")
                new_loc = st.text_input("Nombre", key="nk_loc")
                if st.button("Guardar", key="btn_loc"):
                    if new_loc and add_new_location(new_loc):
                        st.success("Ok")
                        st.rerun()

    # FILA 2: Formulario Datos
    with st.form("entry"):
        c1, c2 = st.columns(2)
        with c1: fecha = st.date_input("Fecha", datetime.now())
        with c2: monto = st.number_input("Monto ($)", min_value=0.0, format="%.2f")
        
        nota = st.text_input("Nota (Opcional)")
        
        st.markdown(f"Resumen: **{tipo_global}** de **${monto}** en **{loc_sel}** ({cat_sel})")
        
        if st.form_submit_button("💾 Guardar Transacción"):
            if monto > 0:
                add_transaction(fecha, tipo_global, cat_sel, monto, nota, loc_sel)
                st.success("Registrado correctamente")
                st.rerun()
            else:
                st.error("Monto inválido")

# --- PESTAÑA 2: DASHBOARD ---
with tab2:
    if not df.empty:
        # KPIs
        ing = df[df['tipo']=='Ingreso']['monto'].sum()
        gas = df[df['tipo']=='Gasto']['monto'].sum()
        k1, k2, k3 = st.columns(3)
        k1.metric("Ingresos", f"${ing:,.0f}")
        k2.metric("Gastos", f"${gas:,.0f}", delta_color="inverse")
        k3.metric("Balance", f"${ing-gas:,.0f}", delta=ing-gas)
        
        st.divider()
        
        # Gráficos
        g1, g2 = st.columns(2)
        with g1:
            st.caption("Por Categoría")
            df_g = df[df['tipo']=='Gasto']
            if not df_g.empty:
                fig = px.pie(df_g, values='monto', names='categoria', hole=0.4)
                fig.update_layout(margin=dict(t=0, b=0, l=0, r=0), showlegend=False)
                st.plotly_chart(fig, use_container_width=True)
        
        with g2:
            st.caption("Por Lugar (Top 5)")
            # Agrupamos por lugar para ver dónde gastas más
            df_loc = df[df['tipo']=='Gasto'].groupby('ubicacion')['monto'].sum().reset_index()
            df_loc = df_loc.sort_values('monto', ascending=False).head(5)
            
            if not df_loc.empty:
                fig2 = px.bar(df_loc, x='monto', y='ubicacion', orientation='h', color='monto')
                fig2.update_layout(margin=dict(t=0, b=0, l=0, r=0), yaxis={'categoryorder':'total ascending'})
                st.plotly_chart(fig2, use_container_width=True)

# --- PESTAÑA 3: GESTIÓN ---
with tab3:
    if not df.empty:
        # Preparamos tabla para ver columnas nuevas
        df_show = df.copy()
        df_show['fecha'] = df_show['fecha'].dt.strftime('%Y-%m-%d')
        st.dataframe(df_show, use_container_width=True)
        
        c_del, c_exp = st.columns(2)
        with c_del:
            uid = st.selectbox("ID a borrar", df['id'].tolist())
            if st.button("Eliminar"):
                delete_transaction(uid)
                st.rerun()
        with c_exp:
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                df_show.to_excel(writer, index=False)
            st.download_button("Descargar Excel", buffer.getvalue(), f"reporte_{titulo}.xlsx")
    else:
        st.info("Sin datos.")