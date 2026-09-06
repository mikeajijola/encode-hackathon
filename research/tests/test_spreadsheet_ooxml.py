import tempfile
import unittest
from pathlib import Path
from zipfile import ZipFile
from openpyxl.styles import PatternFill

from openpyxl import Workbook, load_workbook

from adapters.spreadsheet_diff import diff_workbooks
from adapters.spreadsheet_ooxml import patch_cells_from_candidate, patch_cell_values_raw
from fulfilment import Scope


class TargetedOoxmlPatchTest(unittest.TestCase):
    def test_raw_patch_retains_empty_strings_floats_metadata_merges_styles_and_other_sheet_bytes(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td); original = root / "original.xlsx"; candidate = root / "candidate.xlsx"; output = root / "out.xlsx"
            wb = Workbook(); ws = wb.active; ws.title = "Data"
            ws["A1"] = 1; ws["B1"] = "marker"; ws["C1"] = 0.1
            ws["D1"] = "=COUNTA(B1)"; ws["F1"] = "title"; ws.merge_cells("F1:G1")
            ws["F1"].fill = PatternFill("solid", fgColor="00FF00")
            wb.properties.title = "Preserve"; wb.create_sheet("Other")["A1"] = 3
            wb.save(original); wb.close()
            # Manufacture a literal empty string and high-precision serialized
            # float that ordinary openpyxl save cannot retain exactly.
            with ZipFile(original) as z:
                parts = [(info, z.read(info.filename)) for info in z.infolist()]
            with ZipFile(original, "w") as z:
                for info, value in parts:
                    if info.filename == "xl/worksheets/sheet1.xml":
                        value = value.replace(b">marker<", b"><").replace(b">0.1<", b">0.10000000000000142<")
                    z.writestr(info, value)
            wb = load_workbook(original); wb["Data"]["A1"] = 2; wb["Other"]["A1"] = "corruption"
            wb["Data"]["A1"].fill = PatternFill("solid", fgColor="FF0000")
            wb.save(candidate); wb.close()
            patch_cell_values_raw(original, candidate, output, (Scope("workbook/Data/A1"),))
            wb = load_workbook(output)
            self.assertEqual(wb["Data"]["B1"].value, "")
            self.assertEqual(wb["Data"]["C1"].value, 0.10000000000000142)
            self.assertEqual(wb["Data"]["A1"].value, 2)
            self.assertNotEqual(wb["Data"]["A1"].fill.fgColor.rgb, "00FF0000")
            wb.close()
            with ZipFile(original) as a, ZipFile(output) as b:
                for name in a.namelist():
                    if name != "xl/worksheets/sheet1.xml":
                        self.assertEqual(a.read(name), b.read(name), name)
                import re
                pattern = rb'<c\b(?=[^>]*\br="A1")[^>]*?(?:/>|>.*?</c>)'
                self.assertEqual(re.sub(pattern, b"", a.read("xl/worksheets/sheet1.xml")),
                                 re.sub(pattern, b"", b.read("xl/worksheets/sheet1.xml")))
            self.assertEqual(diff_workbooks(original, output).semantic_scopes, (Scope("workbook/Data/A1"),))

    def test_only_target_sheet_package_part_changes_and_other_semantics_hold(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td); original = root / "original.xlsx"; candidate = root / "candidate.xlsx"
            output = root / "output.xlsx"
            wb = Workbook(); wb.active.title = "Data"; wb["Data"]["A1"] = 1
            wb["Data"]["B1"] = ""; wb.create_sheet("Other")["A1"] = "preserve"
            wb.save(original); wb.close()
            candidate.write_bytes(original.read_bytes())
            wb = load_workbook(candidate); wb["Data"]["A1"] = "=2+2"; wb["Other"]["A1"] = "bad"
            wb.save(candidate); wb.close()
            patch_cells_from_candidate(original, candidate, output, (Scope("workbook/Data/A1"),))
            wb = load_workbook(output, data_only=False)
            self.assertEqual(wb["Data"]["A1"].value, "=2+2")
            self.assertEqual(wb["Other"]["A1"].value, "preserve")
            wb.close()
            result = diff_workbooks(original, output, (Scope("workbook/Data/A1"),))
            self.assertEqual(result.semantic_scopes, (Scope("workbook/Data/A1"),))
            # Formula has no cached value until recalculated; cached projection
            # differs here because the source cell held numeric 1.
            self.assertEqual(result.evaluator_visible_scopes, (Scope("workbook/Data/A1"),))
            self.assertEqual(len(result.representation_parts), 1)


if __name__ == "__main__": unittest.main()
