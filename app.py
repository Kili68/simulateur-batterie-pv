import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from datetime import datetime

from io import StringIO

# === Simulation core ===
def simuler_batterie(prod, conso, capacite_kwh, p_charge_max_kw, p_decharge_max_kw,
                      rendement_pct, soc_min_pct, soc_max_pct, unite):
    rendement = rendement_pct / 100
    soc_min = soc_min_pct / 100 * capacite_kwh
    soc_max = soc_max_pct / 100 * capacite_kwh
    pas_h = 0.25
    soc = soc_min
    soc_series = pd.Series(dtype=float)

    energie_stockee = energie_restituee = energie_exportee = energie_importee = 0
    autoconsommation_brute = consommation_totale = production_totale = 0

    for t in prod.index:
        prod_t = prod.at[t, 'valeur']
        conso_t = conso.at[t, 'valeur']

        surplus = prod_t - conso_t
        consommation_totale += conso_t
        production_totale += prod_t

        if surplus >= 0:
            charge_possible = min(surplus, p_charge_max_kw * pas_h)
            espace_batterie = soc_max - soc
            energie_chargee = min(charge_possible * rendement, espace_batterie)
            soc += energie_chargee
            energie_stockee += energie_chargee
            surplus_rest = surplus - energie_chargee / rendement
            if surplus_rest > 0:
                energie_exportee += surplus_rest
            autoconsommation_brute += conso_t
        else:
            besoin_batterie = min(abs(surplus), p_decharge_max_kw * pas_h)
            energie_disponible = soc - soc_min
            energie_fournie = min(besoin_batterie / rendement, energie_disponible)
            soc -= energie_fournie
            energie_restituee += energie_fournie * rendement
            deficit_rest = abs(surplus) - energie_fournie * rendement
            if deficit_rest > 0:
                energie_importee += deficit_rest
            autoconsommation_brute += prod_t + energie_fournie

        soc_series.at[t] = (soc / capacite_kwh) * 100

    resultats = {
        'soc_series': soc_series,
        'energie_importee': energie_importee,
        'energie_exportee': energie_exportee,
        'energie_stockee': energie_stockee,
        'energie_restituee': energie_restituee,
        'taux_autoconsommation_avec': autoconsommation_brute / production_totale,
        'taux_autarcie_avec': autoconsommation_brute / consommation_totale
    }
    return resultats

# === UI ===
st.set_page_config(layout="wide")
st.title("Simulation de Batterie Photovoltaïque")

fichier_data = st.file_uploader("Fichier CSV (avec horodatage, consommation et production)", type="csv", key="data")

if fichier_data:
    df = pd.read_csv(fichier_data, sep=';')
    st.success("Fichier chargé avec succès.")

    colonnes = df.columns.tolist()
    col_time = st.selectbox("Colonne date/heure", colonnes)
    col_conso = st.selectbox("Colonne consommation", colonnes)
    col_prod = st.selectbox("Colonne production", colonnes)

    unite = st.selectbox("Unité des données", ['Wh', 'kWh', 'W', 'kW'])

    df[col_time] = pd.to_datetime(df[col_time], errors='coerce')
    df = df.dropna(subset=[col_time])
    df = df.set_index(col_time).sort_index()
    df = df[[col_conso, col_prod]].rename(columns={col_conso: 'conso', col_prod: 'prod'})

    if unite == 'W':
        df['conso'] *= 0.25
        df['prod'] *= 0.25
    elif unite == 'kW':
        df['conso'] *= 0.25 * 1000
        df['prod'] *= 0.25 * 1000
    elif unite == 'kWh':
        df['conso'] *= 1000
        df['prod'] *= 1000

    df_conso = df[['conso']].rename(columns={'conso': 'valeur'})
    df_prod = df[['prod']].rename(columns={'prod': 'valeur'})

    st.sidebar.header("Paramètres Batterie")
    capacite = st.sidebar.slider("Capacité utile batterie (kWh)", 1.0, 20.0, 5.0, 0.5)
    p_charge = st.sidebar.slider("Puissance de charge (kW)", 0.5, 10.0, 2.0, 0.5)
    p_decharge = st.sidebar.slider("Puissance de décharge (kW)", 0.5, 10.0, 2.0, 0.5)
    rendement = st.sidebar.slider("Rendement (%)", 70, 100, 90)
    soc_min = st.sidebar.slider("SOC min (%)", 0, 100, 10)
    soc_max = st.sidebar.slider("SOC max (%)", 10, 100, 100)

    bouton_simuler = st.button("Lancer la simulation")

    if bouton_simuler:
        resultats = simuler_batterie(df_prod, df_conso, capacite, p_charge, p_decharge, rendement, soc_min, soc_max, 'Wh')
        soc_series = resultats['soc_series']

        st.subheader("Taux")
        col1, col2 = st.columns(2)
        col1.metric("Taux d'autoconsommation", f"{resultats['taux_autoconsommation_avec'] * 100:.1f} %")
        col2.metric("Taux d'autarcie", f"{resultats['taux_autarcie_avec'] * 100:.1f} %")

        st.subheader("Graphique interactif")
        vue = st.radio("Vue :", ["Jour", "Semaine", "Mois"], horizontal=True)

        df_plot = pd.DataFrame({
            'Production (kWh)': df_prod['valeur'] / 1000,
            'Consommation (kWh)': df_conso['valeur'] / 1000,
            'SOC (%)': soc_series
        })

        if vue == "Jour":
            jours = df_plot.index.normalize().unique()
            jour_select = st.slider("Choisissez le jour", 0, len(jours) - 1, 0)
            selection = df_plot[df_plot.index.normalize() == jours[jour_select]]
        elif vue == "Semaine":
            semaines = df_plot.resample('W').mean().index
            semaine_select = st.slider("Choisissez la semaine", 0, len(semaines) - 1, 0)
            semaine_start = semaines[semaine_select] - pd.Timedelta(days=6)
            selection = df_plot.loc[(df_plot.index >= semaine_start) & (df_plot.index <= semaines[semaine_select])]
        else:
            mois = df_plot.index.to_period("M").unique()
            mois_select = st.slider("Choisissez le mois", 0, len(mois) - 1, 0)
            selection = df_plot[df_plot.index.to_period("M") == mois[mois_select]]

        st.line_chart(selection)

        csv_result = selection.copy()
        csv_result.index.name = "Horodatage"
        st.download_button("Télécharger ce jeu de données", csv_result.to_csv().encode('utf-8'), "resultats_selection.csv", "text/csv")
