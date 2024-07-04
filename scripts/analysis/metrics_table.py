"""Calculate confusion matrix for whether PBE and MACE both predict imaginary modes
for each material at the Gamma point.
"""

# %%
from typing import Literal

import pandas as pd
from IPython.display import display
from pymatviz.io import df_to_html_table, df_to_pdf
from sklearn.metrics import accuracy_score, confusion_matrix, r2_score, roc_auc_score

from ffonons import PAPER_DIR, PDF_FIGS, SITE_FIGS
from ffonons.enums import DB, Key, Model
from ffonons.io import get_df_summary

__author__ = "Janosh Riebesell"
__date__ = "2023-12-15"


# %% compute last phonon DOS peak for each model and MP
imaginary_freq_tol = 0.01
df_summary = get_df_summary(
    which_db := DB.phonon_db, imaginary_freq_tol=imaginary_freq_tol, refresh_cache=False
)


# %% save analyzed MP IDs to CSV for rendering with Typst

# get material IDs where all models have results
idx_n_avail = df_summary[Key.max_freq].unstack().dropna(thresh=4).index

for folder in (
    PAPER_DIR,
    # f"{DATA_DIR}/{which_db}",
):
    df_summary.xs(Key.pbe, level=1).loc[idx_n_avail][
        [Key.formula, Key.supercell, Key.n_sites]
    ].sort_index(key=lambda idx: idx.str.split("-").str[1].astype(int)).to_csv(
        f"{folder}/phonon-analysis-mp-ids.csv"
    )


# %% make dataframe with model regression metrics for phonon DOS and BS predictions
df_regr = pd.DataFrame()
df_regr.index.name = "Model"


for model in Model:
    if model == Key.pbe or model not in df_summary.index.get_level_values(1):
        continue

    df_model = df_summary.loc[idx_n_avail].xs(model, level=1)

    for metric in (Key.dos_mae, Key.ph_dos_r2):
        df_regr.loc[model.label, metric.label] = df_model[metric].mean()

    df_dft = df_summary.xs(Key.pbe, level=1)

    for metric in (
        # Key.last_dos_peak,
        Key.max_freq,
    ):
        diff = df_dft[metric] - df_model[metric]
        ph_freq_mae = diff.abs().mean()
        not_nan = diff.dropna().index
        ph_freq_r2 = r2_score(
            df_dft[metric].loc[not_nan], df_model[metric].loc[not_nan]
        )
        df_regr.loc[model.label, getattr(Key, f"mae_{metric}").label] = ph_freq_mae
        df_regr.loc[model.label, getattr(Key, f"r2_{metric}").label] = ph_freq_r2


# sort by ph DOS MAE
df_regr = df_regr.convert_dtypes().sort_values(by=Key.dos_mae.label).round(2)


# %% make dataframe with model metrics for phonon DOS and BS predictions
dfs_imag: dict[str, pd.DataFrame] = {}
for col in (Key.has_imag_freq, Key.has_imag_gamma_freq):
    df_imag = pd.DataFrame()
    df_imag.index.name = "Model"
    dfs_imag[col] = df_imag

    for model in Model:
        if model == Key.pbe or model not in df_summary.index.get_level_values(1):
            continue

        df_model = df_summary.loc[idx_n_avail].xs(model, level=1)

        df_dft = df_summary.xs(Key.pbe, level=1)
        imag_modes_pred = df_model[col]
        imag_modes_true = df_dft[col].loc[imag_modes_pred.index]
        normalize: Literal["true", "pred", "all", None] = "true"
        conf_mat = confusion_matrix(
            y_true=imag_modes_true, y_pred=imag_modes_pred, normalize=normalize
        )
        (tn, fp), (fn, tp) = conf_mat
        if normalize == "true":
            assert tn + fp == 1
            assert fn + tp == 1
        elif normalize == "pred":
            assert tn + fn == 1
            assert fp + tp == 1
        elif normalize == "all":
            assert tn + fp + fn + tp == 1
        acc = accuracy_score(imag_modes_true, imag_modes_pred)

        precision = tp / (tp + fp)
        recall = tp / (tp + fn)
        f1 = 2 * (precision * recall) / (precision + recall)
        roc_auc = roc_auc_score(imag_modes_true, imag_modes_pred)
        for metric, val in {
            Key.prec_imag_freq: precision,
            Key.recall_imag_freq: recall,
            Key.f1_imag_freq: f1,
            Key.roc_auc_imag_freq: roc_auc,
            Key.acc_imag_freq: acc,
            Key.fpr_imag_freq: fp,
            Key.fnr_imag_freq: fn,
        }.items():
            df_imag.loc[model.label, metric.label] = val

    df_imag = df_imag.sort_values(
        by=Key.roc_auc_imag_freq.label, ascending=False
    ).round(2)


# %% --- vertical metrics table ---
def caption_factory(key: Key) -> str:
    """Make caption for metrics table of classifying imaginary phonon mode."""
    return (
        f"MLFF vs {which_db.label} {key.label} classification<br>"
        f"(N={len(idx_n_avail):,}, imaginary mode tol={imaginary_freq_tol:.2f} THz)<br>"
    )


cmap = "Blues"
regr_metrics_caption = (
    f"Harmonic phonons from MLFF vs PhononDB PBE (N={len(idx_n_avail):,})<br>"
)
clf_caption = caption_factory(Key.has_imag_freq)
clf_gam_caption = caption_factory(Key.has_imag_gamma_freq)
write_to_disk = True
for df_loop, caption, filename in (
    (dfs_imag[Key.has_imag_freq], clf_caption, "ffonon-imag-clf-table"),
    (dfs_imag[Key.has_imag_gamma_freq], clf_gam_caption, "ffonon-imag-gamma-clf-table"),
    # (df_regr, regr_metrics_caption, "ffonon-regr-metrics-table"),
):
    lower_better = [
        col for col in df_loop if any(pat in col for pat in ("MAE", "FNR", "FPR"))
    ]
    higher_better = {*df_loop} - set(lower_better)
    styler = df_loop.T.style.format(
        # render integers without decimal places
        lambda val: (f"{val:.0f}" if val == int(val) else f"{val:.2f}")
        if isinstance(val, float)
        else val,
        precision=2,
        na_rep="-",
    )
    styler.background_gradient(
        cmap=f"{cmap}_r", subset=pd.IndexSlice[[*lower_better], :], axis="columns"
    )
    styler.background_gradient(
        cmap=cmap, subset=pd.IndexSlice[[*higher_better], :], axis="columns"
    )

    # add up/down arrows to indicate which metrics are better when higher/lower
    arrow_suffix = dict.fromkeys(higher_better, " ↑") | dict.fromkeys(
        lower_better, " ↓"
    )
    styler.relabel_index(
        [f"{col}{arrow_suffix.get(col, '')}" for col in styler.data.index], axis="index"
    ).set_uuid("")

    border = "1px solid black"
    styler.set_table_styles(
        [{"selector": "tr", "props": f"border-top: {border}; border-bottom: {border};"}]
    )

    if filename and write_to_disk:
        table_name = f"{filename}-tol={imaginary_freq_tol}"
        pdf_table_path = f"{PDF_FIGS}/{which_db}/{table_name}.pdf"
        df_to_pdf(styler, file_path=pdf_table_path, size="landscape")
        df_to_html_table(styler, file_path=f"{SITE_FIGS}/{table_name}.svelte")

    styler.set_caption(caption)
    display(styler)


# %% --- horizontal metrics table ---
if False:
    lower_better = [
        col for col in df_regr if any(pat in col for pat in ("MAE", "FNR", "FPR"))
    ]
    styler = df_regr.reset_index().style.format(precision=2, na_rep="-")
    styler.background_gradient(cmap=cmap).background_gradient(
        cmap=f"{cmap}_r", subset=lower_better
    )

    arrow_suffix = dict.fromkeys(higher_better, " ↑") | dict.fromkeys(
        lower_better, " ↓"
    )
    styler.relabel_index(
        [f"{col}{arrow_suffix.get(col, '')}" for col in styler.data], axis="columns"
    ).set_uuid("").hide(axis="index")

    df_to_pdf(styler, file_path=f"{PDF_FIGS}/{table_name}.pdf")
    df_to_html_table(styler, file_path=f"{SITE_FIGS}/{table_name}.svelte")
    display(styler)
    styler.set_caption("Metrics for harmonic phonons from ML force fields vs PBE")