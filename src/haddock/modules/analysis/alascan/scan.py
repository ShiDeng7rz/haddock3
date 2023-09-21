"""alascan module."""
import os
import shlex
import subprocess
from pathlib import Path

import pandas as pd

from haddock import log
from haddock.libs.libalign import get_atoms, load_coords
from haddock.modules.analysis.caprieval.capri import CAPRI


ATOMS_TO_BE_MUTATED = ['C', 'N', 'CA', 'O', 'CB']
RES_CODES = dict([
    ("CYS", "C"),
    ("ASP", "D"),
    ("SER", "S"),
    ("GLN", "Q"),
    ("LYS", "K"),
    ("ILE", "I"),
    ("PRO", "P"),
    ("THR", "T"),
    ("PHE", "F"),
    ("ASN", "N"),
    ("GLY", "G"),
    ("HIS", "H"),
    ("LEU", "L"),
    ("ARG", "R"),
    ("TRP", "W"),
    ("ALA", "A"),
    ("VAL", "V"),
    ("GLU", "E"),
    ("TYR", "Y"),
    ("MET", "M"),
    ])


def mutate(pdb_f, target_chain, target_resnum, mut_resname):
    """Mutate a resnum to a resname."""
    mut_pdb_l = []
    resname = ''
    with open(pdb_f, 'r') as fh:
        for line in fh.readlines():
            if line.startswith('ATOM'):
                chain = line[21]
                resnum = int(line[22:26])
                atom_name = line[12:16].strip()
                if target_chain == chain and target_resnum == resnum:
                    if not resname:
                        resname = line[17:20].strip()
                    if atom_name in ATOMS_TO_BE_MUTATED:
                        # mutate
                        line = line[:17] + mut_resname + line[20:]
                        mut_pdb_l.append(line)
                else:
                    mut_pdb_l.append(line)
    mut_id = f'{RES_CODES[resname]}{target_resnum}{RES_CODES[mut_resname]}'
    mut_pdb_fname = Path(
        pdb_f.name.replace('.pdb', f'-{target_chain}_{mut_id}.pdb'))
    with open(mut_pdb_fname, 'w') as fh:
        fh.write(''.join(mut_pdb_l))
    return mut_pdb_fname


def calc_score(pdb_f, run_dir):
    """Calculate the score of a model.

    Parameters
    ----------
    pdb_f : str
        Path to the pdb file.
    run_dir : str
        Path to the run directory.
    
    Returns
    -------
    score : float
        Haddock score.
    vdw : float
        Van der Waals energy.
    elec : float
        Electrostatic energy.
    desolv : float
        Desolvation energy.
    bsa : float
        Buried surface area.
    """
    cmd = f"haddock3-score {pdb_f} --full --run_dir {run_dir}"
    p = subprocess.run(
        shlex.split(cmd),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
        )
    # check if failed
    out = p.stdout.decode("utf-8").split(os.linesep)
    if p.returncode != 0:
        raise Exception("calc_score failed")
    for ln in out:
        if ln.startswith("> HADDOCK-score (emscoring)"):
            score = float(ln.split()[-1])
        if ln.startswith("> vdw"):
            vdw = float(ln.split("vdw=")[1].split(",")[0])
            elec = float(ln.split("elec=")[1].split(",")[0])
            desolv = float(ln.split("desolv=")[1].split(",")[0])
            bsa = float(ln.split("bsa=")[1].split(",")[0])
    return score, vdw, elec, desolv, bsa


def add_zscores(df_scan_clt, column='delta_score'):
    """Add z-scores to the dataframe.

    Parameters
    ----------
    df_scan : pandas.DataFrame
        Dataframe with the scan results for the model.
    
    colunm : str
        Column to calculate the z-score.
    
    Returns
    -------
    df_scan : pandas.DataFrame
        Dataframe with the z-scores added.
    """
    mean_delta = df_scan_clt[column].mean()
    std_delta = df_scan_clt[column].std()
    if std_delta != 0.0:
        df_scan_clt['z_score'] = (df_scan_clt[column] - mean_delta) / std_delta
    else:
        df_scan_clt['z_score'] = 0.0
    return df_scan_clt


def alascan_cluster_analysis(models):
    """Perform cluster analysis on the alascan data.
    
    Parameters
    ----------
    models : list
        List of models.
    """
    clt_scan = {}
    cl_pops = {}
    for native in models:
        cl_id = native.clt_id
        # unclustered models have cl_id = None
        if cl_id is None:
            cl_id = "-"
        if cl_id not in clt_scan:
            clt_scan[cl_id] = {}
            cl_pops[cl_id] = 1
        else:
            cl_pops[cl_id] += 1
        # read the scan file
        alascan_fname = f"scan_{native.file_name}.csv"
        df_scan = pd.read_csv(alascan_fname, sep="\t", comment="#")
        # loop over the scan file
        for row_idx in range(df_scan.shape[0]):
            row = df_scan.iloc[row_idx]
            chain = row['chain']
            res = row['res']
            ori_resname = row['ori_resname']
            delta_score = row['delta_score']
            delta_vdw = row['delta_vdw']
            delta_elec = row['delta_elec']
            delta_desolv = row['delta_desolv']
            delta_bsa = row['delta_bsa']
            # add to the cluster data with the ident logic
            ident = f"{chain}-{res}-{ori_resname}"
            if ident not in clt_scan[cl_id]:
                clt_scan[cl_id][ident] = {
                    'delta_score': delta_score,
                    'delta_vdw': delta_vdw,
                    'delta_elec': delta_elec,
                    'delta_desolv': delta_desolv,
                    'delta_bsa': delta_bsa,
                    'frac_pr': 1
                    }
            else:
                clt_scan[cl_id][ident]['delta_score'] += delta_score
                clt_scan[cl_id][ident]['delta_vdw'] += delta_vdw
                clt_scan[cl_id][ident]['delta_elec'] += delta_elec
                clt_scan[cl_id][ident]['delta_desolv'] += delta_desolv
                clt_scan[cl_id][ident]['delta_bsa'] += delta_bsa
                clt_scan[cl_id][ident]['frac_pr'] += 1
    # now average the data
    for cl_id in clt_scan:
        scan_clt_filename = f"scan_clt_{cl_id}.csv"
        log.info(f"Writing {scan_clt_filename}")
        clt_data = []
        for ident in clt_scan[cl_id]:
            chain = ident.split("-")[0]
            resnum = ident.split("-")[1]
            resname = ident.split("-")[2]
            frac_pr = clt_scan[cl_id][ident]["frac_pr"]
            clt_data.append([chain, resnum, resname, ident,
                             clt_scan[cl_id][ident]['delta_score'] / frac_pr,
                             clt_scan[cl_id][ident]['delta_vdw'] / frac_pr,
                             clt_scan[cl_id][ident]['delta_elec'] / frac_pr,
                             clt_scan[cl_id][ident]['delta_desolv'] / frac_pr,
                             clt_scan[cl_id][ident]['delta_bsa'] / frac_pr,
                             clt_scan[cl_id][ident]['frac_pr'] / cl_pops[cl_id]
                             ]
                            )
        df_cols = ['chain', 'resnum', 'resname', 'full_resname', 'delta_score',
                   'delta_vdw', 'delta_elec', 'delta_desolv', 'delta_bsa',
                   'frac_pres']
        df_scan_clt = pd.DataFrame(clt_data, columns=df_cols)
        # adding clt-based Z score
        df_scan_clt = add_zscores(df_scan_clt, 'delta_score')

        df_scan_clt.sort_values(by=['chain', 'resnum'], inplace=True)
        df_scan_clt.to_csv(
            scan_clt_filename,
            index=False,
            float_format='%.3f',
            sep="\t")
    return clt_scan


class ScanJob:
    """A Job dedicated to the parallel alanine scanning of models."""

    def __init__(
            self,
            output,
            params,
            scan_obj):

        log.info(f"core {scan_obj.core}, initialising Scan...")
        self.output = output
        self.params = params
        self.scan_obj = scan_obj

    def run(self):
        """Run this ScanJob."""
        log.info(f"core {self.scan_obj.core}, running Scan...")
        self.scan_obj.run()
        self.scan_obj.output()
        return


class Scan:
    """Contact class."""

    def __init__(
            self,
            model_list,
            output_name,
            core,
            path,
            **params,
            ):
        """Initialise Contact class."""
        self.model_list = model_list
        self.output_name = output_name
        self.core = core
        self.path = path
        self.scan_res = params['params']['scan_residue']

    def run(self):
        """Run alascan calculations."""
        for native in self.model_list:
            # original score from the workflow
            ori_score = native.score
            try:
                ori_score = float(ori_score)
            except ValueError:
                ori_score = float('nan')
            # here we rescore the native model for consistency, as the ori_score
            # could come from any module in principle
            sc_dir = f"haddock3-score-{self.core}"
            n_score, n_vdw, n_elec, n_des, n_bsa = calc_score(native.rel_path,
                                                              run_dir=sc_dir)
            
            scan_data = []
            interface = CAPRI.identify_interface(native.rel_path)
            atoms = get_atoms(native.rel_path)
            coords, chain_ranges = load_coords(native.rel_path,
                                               atoms,
                                               add_resname=True
                                               )
            resname_dict = {}
            for chain, resid, _atom, resname in coords.keys():
                key = f"{chain}-{resid}"
                if key not in resname_dict:
                    resname_dict[key] = resname
            # self.log(f'Mutating interface of {native.file_name}...')
            # self.log(f"Interface: {interface}")
            for chain in interface:
                for res in interface[chain]:
                    ori_resname = resname_dict[f"{chain}-{res}"]
                    end_resname = self.scan_res
                    if ori_resname == self.scan_res:
                        # we do not re-score
                        c_score = n_score
                        c_vdw = n_vdw
                        c_elec = n_elec
                        c_des = n_des
                        c_bsa = n_bsa
                    else:
                        mut_pdb_name = mutate(native.rel_path,
                                              chain,
                                              res,
                                              end_resname)
                        c_score, c_vdw, c_elec, c_des, c_bsa = calc_score(
                            mut_pdb_name,
                            run_dir=sc_dir)
                        # difference with the original score
                        if ori_score != float('nan'):
                            delta_ori_score = c_score - ori_score
                        # now the deltas with the native
                        delta_score = c_score - n_score
                        delta_vdw = c_vdw - n_vdw
                        delta_elec = c_elec - n_elec
                        delta_desolv = c_des - n_des
                        delta_bsa = c_bsa - n_bsa
 
                        scan_data.append([chain, res, ori_resname, end_resname,
                                          c_score, c_vdw, c_elec, c_des,
                                          c_bsa, delta_ori_score, delta_score,
                                          delta_vdw, delta_elec, delta_desolv,
                                          delta_bsa])
                        os.remove(mut_pdb_name)
            # write output
            df_columns = ['chain', 'res', 'ori_resname', 'end_resname',
                          'score', 'vdw', 'elec', 'desolv', 'bsa',
                          'delta_ori_score', 'delta_score', 'delta_vdw',
                          'delta_elec', 'delta_desolv', 'delta_bsa']
            df_scan = pd.DataFrame(scan_data, columns=df_columns)
            alascan_fname = f"scan_{native.file_name}.csv"
            # add zscore
            df_scan = add_zscores(df_scan, 'delta_score')

            df_scan.to_csv(
                alascan_fname,
                index=False,
                float_format='%.3f',
                sep="\t"
                )

            fl_content = open(alascan_fname, 'r').read()
            with open(alascan_fname, 'w') as f:
                f.write(f"########################################{os.linesep}")  # noqa E501
                f.write(f"# `alascan` results for {native.file_name}{os.linesep}")  # noqa E501
                f.write(f"#{os.linesep}")
                f.write(f"########################################{os.linesep}")  # noqa E501
                f.write(fl_content)
    
    def output(self):
        """Write down unique contacts to file."""
        output_fname = Path(self.path, self.output_name)
        with open(output_fname, "w") as out_fh:
            out_fh.write(
                f"core {self.core} wrote alascan data "
                f"for {len(self.model_list)} models{os.linesep}"
                )
