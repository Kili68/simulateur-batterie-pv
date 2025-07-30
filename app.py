import streamlit as st
import pandas as pd

st.title("Simulation Batterie Photovoltaïque")

# Upload
csv_file = st.file_uploader("Chargez un fichier CSV", type="csv")

if csv_file:
    df = pd.read_csv(csv_file)
    st.write("Aperçu des données :", df.head())

    # Sélection des colonnes
    col_conso = st.selectbox("Colonne consommation", df.columns)
    col_prod = st.selectbox("Colonne production", df.columns)
    interval = st.selectbox("Intervalle (heures)", [0.25, 1.0], index=0)

    # Paramètres batterie
    capacity = st.slider("Capacité batterie (kWh)", 1.0, 20.0, 5.0)
    pmax = st.slider("Puissance max (kW)", 1.0, 10.0, 3.0)
    eff = st.slider("Rendement (%)", 70, 100, 90)

    # Bouton simulation
    if st.button("Lancer la simulation"):
        df["Energie nette"] = df[col_conso] - df[col_prod]
        df["SOC"] = 0.0
        soc = 0.0
        soc_list = []

        for net in df["Energie nette"]:
            variation = 0.0
            if net < 0:
                # Charge
                charge_max = min(-net * (eff/100), capacity - soc, pmax * interval)
                variation = charge_max
            else:
                # Décharge
                discharge_max = min(net / (eff/100), soc, pmax * interval)
                variation = -discharge_max
            soc += variation
            soc = max(0.0, min(capacity, soc))
            soc_list.append(soc)

        df["SOC (kWh)"] = soc_list
        df["SOC (%)"] = df["SOC (kWh)"] / capacity * 100
        st.line_chart(df["SOC (%)"])
        st.download_button("Télécharger résultats", df.to_csv(index=False), "simulation.csv", "text/csv")
