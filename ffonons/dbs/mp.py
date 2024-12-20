"""Download MP phonon docs."""

import json
import os
from typing import TYPE_CHECKING

from emmet.core.phonon import PhononBSDOSDoc
from monty.io import zopen
from monty.json import MontyEncoder
from mp_api.client import MPRester

from ffonons import DATA_DIR

if TYPE_CHECKING:
    from pymatgen.core import Structure

__author__ = "Janosh Riebesell"
__date__ = "2023-12-07"


def get_mp_ph_docs(
    mp_id: str, docs_dir: str = f"{DATA_DIR}/mp"
) -> tuple[PhononBSDOSDoc, str]:
    """Get phonon data from MP and save it to disk.

    Args:
        mp_id (str): Material ID.
        docs_dir (str): Directory to save the MP phonon doc. Set to "" to not save.
            Defaults to ffonons.DATA_DIR.

    Returns:
        tuple[PhononBSDOSDoc, str]: Phonon doc and path to saved doc.
    """
    mp_rester = MPRester(mute_progress_bars=True)
    struct: Structure = mp_rester.get_structure_by_material_id(mp_id)

    id_formula = f"{mp_id}-{struct.formula.replace(' ', '')}"
    mp_ph_doc_path = f"{docs_dir}/{id_formula}.json.xz" if docs_dir else ""

    if os.path.isfile(mp_ph_doc_path):
        with zopen(mp_ph_doc_path, mode="rt") as file:
            mp_phonon_doc = json.load(file)
    else:
        mp_phonon_doc = mp_rester.materials.phonon.get_data_by_id(mp_id)
        if mp_ph_doc_path:
            with zopen(mp_ph_doc_path, mode="wt") as file:
                json.dump(mp_phonon_doc, file, cls=MontyEncoder)

    return mp_phonon_doc, mp_ph_doc_path
