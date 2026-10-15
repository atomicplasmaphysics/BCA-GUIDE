import shutil

import pytest

from conftest import SIMULATION_PROGRAMS, DATA

from Containers.CrystalTableFile import CrystalTableFile, TableCrystal, CrystalTableError
from Utility.CrystalImport import importCrystal, CrystalImportError


TABLES = sorted(SIMULATION_PROGRAMS.glob('SDTrimSP/*/tables/table.crystal'))


@pytest.mark.parametrize('table', TABLES, ids=lambda path: path.parents[1].name)
def test_read_table(table):
    table_file = CrystalTableFile(table)
    assert table_file.structures
    assert table_file.crystals
    for crystal in table_file.crystals:
        structure = table_file.structure(crystal.structure)
        assert structure is not None
        assert len(structure.positions) == len(crystal.elements)


@pytest.fixture
def table_copy(tmp_path):
    if not TABLES:
        pytest.skip('no table.crystal found')
    shutil.copy(TABLES[-1], tmp_path / 'table.crystal')
    return CrystalTableFile(tmp_path / 'table.crystal')


def test_add_crystal_existing_structure(table_copy):
    fcc = [(0.5, 0.5, 0.), (0., 0., 0.), (0., 0.5, 0.5), (0.5, 0., 0.5)]
    crystal = table_copy.addCrystal(TableCrystal('Au_fcc', 4.078, 4.078, 4.078, 0.05898, elements=['Au'] * 4), fcc)
    assert table_copy.structure(crystal.structure).name == 'fcc-type'

    reread = CrystalTableFile(table_copy.path)
    assert reread.crystal('Au_fcc') is not None
    assert len(reread.structures) == len(table_copy.structures)
    assert table_copy.path.with_name('table.crystal.bck').exists()


def test_add_crystal_new_structure(table_copy):
    count = len(table_copy.structures)
    crystal = table_copy.addCrystal(TableCrystal('TiO_test', 3., 3., 5., 0.03, elements=['Ti', 'Ti', 'O']), [(0, 0, 0), (0.5, 0.5, 0.5), (0.3, 0.3, 0)])
    reread = CrystalTableFile(table_copy.path)
    assert len(reread.structures) == count + 1
    assert reread.crystal('TiO_test').structure == crystal.structure


def test_reordered_elements(table_copy):
    # positions of the bcc structure in reversed order, elements must be reordered accordingly
    crystal = table_copy.addCrystal(TableCrystal('CsCl_test', 4.12, 4.12, 4.12, 0.0286, elements=['Cl', 'Cs']), [(0.5, 0.5, 0.5), (0, 0, 0)])
    assert crystal.elements == ['Cs', 'Cl']


@pytest.mark.parametrize('crystal, positions', [
    (TableCrystal('name with space', 1, 1, 1, 1, elements=['Cu']), [(0, 0, 0)]),
    (TableCrystal('much_too_long_name', 1, 1, 1, 1, elements=['Cu']), [(0, 0, 0)]),
    (TableCrystal('dy_differs', 1, 2, 1, 1, elements=['Cu']), [(0, 0, 0)]),
    (TableCrystal('too_many', 1, 1, 1, 1, elements=['Cu'] * 9), [(i / 9, 0, 0) for i in range(9)]),
])
def test_invalid_crystals(table_copy, crystal, positions):
    with pytest.raises(CrystalTableError):
        table_copy.addCrystal(crystal, positions)


def test_duplicate_name(table_copy):
    name = table_copy.crystals[0].name
    with pytest.raises(CrystalTableError):
        table_copy.addCrystal(TableCrystal(name, 1, 1, 1, 1, elements=['Cu']), [(0, 0, 0)])


def test_import_cif_with_symmetry():
    crystal = importCrystal(DATA / 'NaCl.cif')
    assert crystal.isOrthogonal()
    assert crystal.lengths[0] == pytest.approx(5.640487)
    assert sorted(crystal.elements) == ['Cl'] * 4 + ['Na'] * 4


def test_import_poscar():
    crystal = importCrystal(DATA / 'Si_diamond.vasp')
    assert crystal.elements == ['Si'] * 8
    assert crystal.lengths == pytest.approx((5.431, 5.431, 5.431))


def test_import_matches_table_structures():
    if not TABLES:
        pytest.skip('no table.crystal found')
    table_file = CrystalTableFile(TABLES[-1])
    for file, structure_name in [('NaCl.cif', 'NaCl-type'), ('Si_diamond.vasp', 'diamond-type')]:
        crystal = importCrystal(DATA / file)
        structure, order = table_file.findStructure(crystal.positions)
        assert structure is not None and structure.name == structure_name


def test_import_hexagonal_is_not_orthogonal():
    assert not importCrystal(DATA / 'Mg_hcp.cif').isOrthogonal()


def test_import_unknown_format(tmp_path):
    (tmp_path / 'crystal.xyz').write_text('')
    with pytest.raises(CrystalImportError):
        importCrystal(tmp_path / 'crystal.xyz')
