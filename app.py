from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import streamlit as st

DOSSIER = Path(__file__).parent / "donnees"

st.set_page_config(page_title="L'électricité dans 12 quartiers", layout="wide")
st.title("L'électricité dans 12 quartiers")


@st.cache_data
def charger_donnees():
    return pd.read_csv(DOSSIER / "consommation_propre.csv")


df = charger_donnees()

st.write(
    "Une compagnie d'électricité a relevé chaque mois, de janvier 2024 à décembre 2025, "
    "la consommation de 12 quartiers de Port-au-Prince, Delmas, Pétion-Ville et Cap-Haïtien."
)
st.write("Le directeur veut savoir si la consommation suit la chaleur ou les heures de courant.")


def fr(nombre, decimales=1):
    return f"{nombre:,.{decimales}f}".replace(",", " ").replace(".", ",")


def tracer_nuage(ax, x, y, couleur):
    ax.scatter(x, y, alpha=0.6, color=couleur)
    pente, origine = np.polyfit(x, y, 1)
    ax.plot(x.sort_values(), pente * x.sort_values() + origine, color="black")


communes = sorted(df["commune"].unique())
choix_communes = st.sidebar.multiselect("Communes", communes, default=communes)

annees = sorted(df["annee"].unique())
choix_annee = st.sidebar.selectbox("Année", annees, index=annees.index(2025))

if not choix_communes:
    st.warning("Choisissez au moins une commune dans la barre latérale.")
    st.stop()

filtre = df[df["commune"].isin(choix_communes) & (df["annee"] == choix_annee)]

col1, col2, col3 = st.columns(3)
col1.metric("Consommation totale", f"{fr(filtre['kwh'].sum() / 1e6, 2)} millions de kWh")
col2.metric("Consommation par abonné", f"{fr(filtre['kwh_par_abonne'].mean())} kWh")
col3.metric("Heures de courant par jour", f"{fr(filtre['heures_courant'].mean())} h")

onglet1, onglet2, onglet3, onglet4, onglet5 = st.tabs(
    ["Par abonné", "Évolution par commune", "Chaleur ou courant ?", "Coupures", "Relevés records"]
)

with onglet1:
    classement = (
        filtre.groupby(["quartier", "type"], as_index=False)["kwh_par_abonne"]
        .mean()
        .sort_values("kwh_par_abonne", ascending=False)
    )
    couleurs = classement["type"].map({"Commercial": "#17684d", "Résidentiel": "#d47a45"})
    fig, ax = plt.subplots(figsize=(9, 5))
    ax.barh(classement["quartier"], classement["kwh_par_abonne"], color=couleurs)
    ax.invert_yaxis()
    ax.set(title="Consommation moyenne par abonné", xlabel="kWh par abonné et par mois", ylabel="")
    st.pyplot(fig)

    premier = classement.iloc[0]
    st.write(
        f"En {choix_annee}, {premier['quartier']} arrive en tête avec "
        f"{fr(premier['kwh_par_abonne'])} kWh par abonné et par mois."
    )

with onglet2:
    abonnes_commune = df.groupby(["commune", "quartier"])["abonnes"].first().groupby("commune").sum()
    mensuel = filtre.groupby(["commune", "mois"], as_index=False)["kwh"].sum()
    mensuel["kwh_par_abonne"] = mensuel["kwh"] / mensuel["commune"].map(abonnes_commune)

    fig, ax = plt.subplots(figsize=(10, 4.5))
    for commune, groupe in mensuel.groupby("commune"):
        ax.plot(groupe["mois"], groupe["kwh_par_abonne"], marker="o", label=commune)
    ax.legend()
    ax.set(title=f"Consommation mensuelle par abonné en {choix_annee}", xlabel="", ylabel="kWh par abonné")
    ax.tick_params(axis="x", rotation=45)
    st.pyplot(fig)

    totaux = df[df["commune"].isin(choix_communes)].pivot_table(
        index="commune", columns="annee", values="kwh", aggfunc="sum"
    )
    hausse = ((totaux[2025] - totaux[2024]) / totaux[2024] * 100).sort_values(ascending=False)
    st.write(
        f"De 2024 à 2025, la plus forte hausse est à {hausse.index[0]} (+{fr(hausse.iloc[0])} %) "
        f"et la plus faible à {hausse.index[-1]} (+{fr(hausse.iloc[-1])} %)."
    )

with onglet3:
    residentiel = df[df["commune"].isin(choix_communes) & (df["type"] == "Résidentiel")]
    if len(residentiel) < 3:
        st.info("Pas assez de relevés résidentiels pour calculer une corrélation.")
    else:
        r_heures = residentiel["kwh_par_abonne"].corr(residentiel["heures_courant"])
        r_temp = residentiel["kwh_par_abonne"].corr(residentiel["temperature_c"])

        fig, axes = plt.subplots(1, 2, figsize=(11, 4.5), sharey=True)
        tracer_nuage(axes[0], residentiel["heures_courant"], residentiel["kwh_par_abonne"], "#17684d")
        axes[0].set(title="Heures de courant", xlabel="Heures par jour", ylabel="kWh par abonné")
        tracer_nuage(axes[1], residentiel["temperature_c"], residentiel["kwh_par_abonne"], "#d47a45")
        axes[1].set(title="Température", xlabel="Température (°C)", ylabel="")
        st.pyplot(fig)

        st.write(
            f"Quartiers résidentiels en 2024 et 2025 : la corrélation est de {fr(r_heures, 2)} "
            f"avec les heures de courant et de {fr(r_temp, 2)} avec la température."
        )

with onglet4:
    fig, ax = plt.subplots(figsize=(9, 4.5))
    noms = sorted(filtre["commune"].unique())
    ax.boxplot([filtre.loc[filtre["commune"] == c, "heures_courant"] for c in noms])
    ax.set_xticks(range(1, len(noms) + 1), noms)
    ax.axhline(8, color="red", linestyle="--")
    ax.set(title=f"Heures de courant par jour en {choix_annee}", xlabel="", ylabel="Heures par jour")
    st.pyplot(fig)

    medianes = filtre.groupby("commune")["heures_courant"].median().sort_values()
    sous_8h = filtre[filtre["heures_courant"] < 8]
    st.write(
        f"La médiane la plus basse est à {medianes.index[0]} avec {fr(medianes.iloc[0])} h par jour. "
        f"En {choix_annee}, {len(sous_8h)} relevés passent sous 8 heures de courant par jour."
    )

with onglet5:
    top3 = filtre.nlargest(3, "kwh")
    fig, ax = plt.subplots(figsize=(8, 3))
    ax.barh(top3["quartier"] + " " + top3["mois"], top3["kwh"], color="#17684d")
    ax.invert_yaxis()
    ax.set(title="Les 3 plus grosses consommations mensuelles", xlabel="kWh")
    st.pyplot(fig)

    record = top3.iloc[0]
    st.write(f"Le record est {record['quartier']} en {record['mois']} avec {fr(record['kwh'], 0)} kWh.")

st.markdown(
    """
### Conclusion

La consommation suit les heures de courant, pas la chaleur : dans les quartiers résidentiels,
la corrélation est de 0,76 avec les heures de courant et de -0,15 avec la température.
Une corrélation montre un lien, pas une cause.
"""
)

with st.expander("Voir les données filtrées"):
    st.dataframe(filtre, hide_index=True)
