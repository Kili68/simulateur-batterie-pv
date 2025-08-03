import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from datetime import datetime
import csv
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
    puissances_prod = []
    puissances_conso = []

    for t in prod.index:
        prod_t = prod.at[t, 'valeur']
        conso_t = conso.at[t, 'valeur']
        puissances_prod.append(prod_t)
        puissances_conso.append(conso_t)

        surplus = prod_t - conso_t
        consommation_totale += conso_t
        production_totale += prod_t

        if surplus >= 0:
            energie_chargeable = min(surplus, p_charge_max_kw * pas_h, (soc_max - soc) / rendement)
            energie_chargee = energie_chargeable * rendement
            soc += energie_chargee
            energie_stockee += energie_chargee
            surplus_rest = surplus - energie_chargeable
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

    energie_importee_sans = (conso['valeur'] - prod['valeur']).clip(lower=0).sum()
    energie_exportee_sans = (prod['valeur'] - conso['valeur']).clip(lower=0).sum()
    autoconsommation_sans = np.minimum(prod['valeur'], conso['valeur']).sum()
    taux_autoconsommation_sans = autoconsommation_sans / production_totale
    taux_autarcie_sans = autoconsommation_sans / consommation_totale

    resultats = {
        'soc_series': soc_series,
        'energie_importee': energie_importee,
        'energie_exportee': energie_exportee,
        'energie_importee_sans': energie_importee_sans,
        'energie_exportee_sans': energie_exportee_sans,
        'energie_stockee': energie_stockee,
        'energie_restituee': energie_restituee,
        'taux_autoconsommation_avec': autoconsommation_brute / production_totale,
        'taux_autarcie_avec': autoconsommation_brute / consommation_totale,
        'taux_autoconsommation_sans': taux_autoconsommation_sans,
        'taux_autarcie_sans': taux_autarcie_sans,
        'autoconsommation_brute': autoconsommation_brute,
        'production_totale': production_totale,
        'consommation_totale': consommation_totale,
        'puissance_max_prod': max(puissances_prod) * 4 / 1000,
        'puissance_max_conso': max(puissances_conso) * 4 / 1000,
    }
    return resultats

# === UI ===
st.set_page_config(layout="wide")
st.title("Simulation de Batterie Photovoltaïque")

fichier_data = st.file_uploader("Fichier CSV (avec horodatage, consommation et production)", type="csv", key="data")

if fichier_data:
    contenu = fichier_data.read().decode("utf-8")
    separateur = csv.Sniffer().sniff(contenu[:1024]).delimiter
    st.info(f"Séparateur détecté : '{separateur}'")
    fichier_data.seek(0)

    df = pd.read_csv(fichier_data, sep=separateur)
    st.subheader("Aperçu des données")
    st.dataframe(df.head(20))

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

    st.subheader("Analyse sans batterie")
    energie_importee_sans = (df['conso'] - df['prod']).clip(lower=0).sum()
    energie_exportee_sans = (df['prod'] - df['conso']).clip(lower=0).sum()
    autoconsommation_sans = np.minimum(df['conso'], df['prod']).sum()
    taux_autoconsommation_sans = autoconsommation_sans / df['prod'].sum()
    taux_autarcie_sans = autoconsommation_sans / df['conso'].sum()

    col1, col2, col3 = st.columns(3)
    col1.metric("Taux d'autoconsommation", f"{taux_autoconsommation_sans * 100:.1f} %")
    col2.metric("Taux d'autarcie", f"{taux_autarcie_sans * 100:.1f} %")
    col3.metric("Puissance max consommée (kW)", f"{(df['conso'].max() * 4 / 1000):.2f}")

    st.markdown(f"**Energie totale consommée :** {df['conso'].sum() / 1000:.1f} kWh")
    st.markdown(f"**Energie totale produite :** {df['prod'].sum() / 1000:.1f} kWh")
    st.markdown(f"**Puissance max produite :** {df['prod'].max() * 4 / 1000:.2f} kW")
    st.markdown(f"**Energie importée :** {energie_importee_sans / 1000:.1f} kWh")
    st.markdown(f"**Energie exportée :** {energie_exportee_sans / 1000:.1f} kWh")

    with st.sidebar:
        st.header("Paramètres Batterie")
        capacite = st.slider("Capacité utile batterie (kWh)", 1.0, 20.0, 5.0, 0.5)
        p_charge = st.slider("Puissance de charge (kW)", 0.5, 10.0, 2.0, 0.5)
        p_decharge = st.slider("Puissance de décharge (kW)", 0.5, 10.0, 2.0, 0.5)
        rendement = st.slider("Rendement (%)", 70, 100, 90)
        soc_min = st.slider("SOC min (%)", 0, 100, 10)
        soc_max = st.slider("SOC max (%)", 10, 100, 100)
        bouton_simuler = st.button("Lancer la simulation avec batterie")

    if bouton_simuler:
        with st.spinner("Simulation en cours..."):
            df_conso_copy = df_conso.copy()
            df_prod_copy = df_prod.copy()
            resultats = simuler_batterie(df_prod_copy, df_conso_copy, capacite, p_charge, p_decharge, rendement, soc_min, soc_max, 'Wh')

        st.subheader("Comparaison avec batterie")
        col1, col2, col3 = st.columns(3)
        col1.metric("Taux d'autoconsommation", f"{resultats['taux_autoconsommation_avec'] * 100:.1f} %")
        col2.metric("Taux d'autarcie", f"{resultats['taux_autarcie_avec'] * 100:.1f} %")
        col3.metric("Puissance max consommée (kW)", f"{resultats['puissance_max_conso']:.2f}")

        st.markdown(f"**Energie totale consommée :** {resultats['consommation_totale'] / 1000:.1f} kWh")
        st.markdown(f"**Energie totale produite :** {resultats['production_totale'] / 1000:.1f} kWh")
        st.markdown(f"**Puissance max produite :** {resultats['puissance_max_prod']:.2f} kW")
        st.markdown(f"**Energie importée :** {resultats['energie_importee'] / 1000:.1f} kWh")
        st.markdown(f"**Energie exportée :** {resultats['energie_exportee'] / 1000:.1f} kWh")
        st.markdown(f"**Energie stockée :** {resultats['energie_stockee'] / 1000:.1f} kWh")
        st.markdown(f"**Energie restituée :** {resultats['energie_restituee'] / 1000:.1f} kWh")

        st.subheader("Tableau comparatif")
        tableau = pd.DataFrame({
            "Indicateur": [
                "Taux d'autoconsommation", "Taux d'autarcie", "Énergie importée (kWh)", "Énergie exportée (kWh)"
            ],
            "Sans batterie": [
                f"{resultats['taux_autoconsommation_sans']*100:.1f} %",
                f"{resultats['taux_autarcie_sans']*100:.1f} %",
                f"{resultats['energie_importee_sans']/1000:.1f}",
                f"{resultats['energie_exportee_sans']/1000:.1f}"
            ],
            "Avec batterie": [
                f"{resultats['taux_autoconsommation_avec']*100:.1f} %",
                f"{resultats['taux_autarcie_avec']*100:.1f} %",
                f"{resultats['energie_importee']/1000:.1f}",
                f"{resultats['energie_exportee']/1000:.1f}"
            ]
        })
        st.dataframe(tableau, use_container_width=True)
