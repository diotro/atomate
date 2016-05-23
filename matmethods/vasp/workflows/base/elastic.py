# coding: utf-8

from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

import os

from fireworks import Workflow

from matmethods.vasp.fireworks.core import OptimizeFW, TransmuterFW
from pymatgen.io.vasp.sets import MPVaspInputSet
from pymatgen.transformations.standard_transformations import \
    DeformStructureTransformation

"""
This module defines the elastic workflow
"""


__author__ = 'Shyam Dwaraknath, Joseph Montoya'
__email__ = 'shyamd@lbl.gov, montoyjh@lbl.gov'


@explicit_serialize
class PassStressStrainData(FireTaskBase):
    """
    Passes the stress and deformation for an elastic deformation calculation

    Required params:
        deformation: the deformation gradient used in the elastic analysis.

    """

    required_params = ["deformation"]

    def run_task(self, fw_spec):
        v = Vasprun('Vasprun.xml')
        stress = v['ionic_steps'][-1]['stress']
        return FWAction(mod_spec=[{'_push': {'deformation': self['deformation'], 'stress': stress}}])


def get_wf_elastic_constant(structure, max_norm_deformation=0.01, max_shear_deformation=0.08,
                            num_norm=4, num_shear=4, vasp_input_set=None, vasp_cmd="vasp", db_file=None):
    """
    Returns a workflow to calculate elastic consants. This workflow is dynamic

    Firework 1 : write vasp input set for structural relaxation,
                 run vasp,
                 pass run location,
                 database insertion.

    Firework 2: Determine which deformations to run based on symmetry if needed
                TODO: How to turn off children selectively?

    Firework 3 - N: Optimize Deformed Structure

    Firework N: Analyze Deformations


    Args:
        structure (Structure): input structure to be optimized and run
        vasp_input_set (DictVaspInputSet): vasp input set.
        vasp_cmd (str): command to run
        db_file (str): path to file containing the database credentials.

    Returns:
        Workflow
    """

    v = vasp_input_set or MPVaspInputSet(force_gamma=True)

    fws = []

    fws.append(OptimizeFW(structure=structure))

    norm_deformations = np.linspace(-max_norm_deformation, max_norm_deformation, num=num_norm)
    norm_deformations = norm_deformations[norm_deformations.nonzero()]
    shear_deformations = np.linspace(-max_shear_deformation, max_shear_deformation, num=num_shear)
    shear_deformations = shear_deformations[shear_deformations.nonzero()]

    deformations = []

    # Generate deformations
    for ind in [(0, 0), (1, 1), (2, 2)]:
        for amount in norm_deformations:
            defo = Deformation.from_index_amount(ind, amount)
            deformations.append(defo)

    for ind in [(0, 1), (0, 2), (1, 2)]:
        for amount in shear_deformations:
            defo = Deformation.from_index_amount(ind, amount)
            deformations.append(defo)

    for deformation in deformations:
        fw = TransmuterFW(structure=strcuture,
                          transformations=[DeformStructureTransformation],
                          transformation_params=[
                              {"deformation": deformation.tolist()}],
                          parents=fws[0])

        fw['_tasks'].append(PassStressStrainData(deformation=deformation.tolist()))
        fws.append(fw)

    # TODO: Analyze the data -  OR MAYBE THIS SHOULD BE A BUILDER ????


def symm_reduce(self, symm_ops, deformation_list, tolerance=1e-2):
    """
    Checks list of deformation gradient tensors for symmetrical
    equivalents and returns a new list with reduntant ones removed

    Args:
        symm_ops (list of SymmOps): list of SymmOps objects with which
            to check the list of deformation tensors for duplicates
        deformation_list (list of Deformations): list of deformation
            gradient objects to check for duplicates
        tolerance (float): tolerance for assigning equal defo. gradients
    """
    unique_defos = []
    for defo in deformation_list:
        in_unique = False
        for op in symm_ops:
            if np.any([(np.abs(defo - defo.transform(symm_op)) < tol).all()
                       for unique_defo in unique_defos]):
                in_unique = True
                break
        if not in_unique:
            unique_defos += [defo]
    return unique_defos


if __name__ == "__main__":
    from pymatgen.util.testing import PymatgenTest

    structure = PymatgenTest.get_structure("Si")
    wf = get_wf_elastic_constant(structure)
