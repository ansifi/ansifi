from decimal import Decimal
import unittest

import ansif_books


class AnsifBooksTests(unittest.TestCase):
    def test_interest_category(self):
        cat, memo = ansif_books.categorize("INT.PD 01-04-2025 TO 30-06-2025", Decimal("120.00"), Decimal("0"))
        self.assertEqual(cat, "income_interest")
        self.assertIn("Interest", memo)

    def test_salary_credit(self):
        cat, _ = ansif_books.categorize("NEFT-SEVENDYNE CONSULTANCY SALARY", Decimal("190000"), Decimal("0"))
        self.assertEqual(cat, "income_salary")

    def test_sbi_tsv_credit_debit(self):
        from sib_statement import parse_sbi_tsv

        text = (
            "Account Number     :\t_00000020161325222\n"
            "Txn Date\tValue Date\tDescription\tRef\tDebit\tCredit\tBalance\t\n"
            "1 Apr 2024\t1 Apr 2024\t   BY TRANSFER-INB salary\tSEVENDYNE\t \t40,000.00\t41,462.60\n"
            "2 Apr 2024\t2 Apr 2024\t   TO TRANSFER-UPI/DR/1\tTRANSFER TO\t200.00\t \t41,262.60\n"
        )
        acct, _, _, rows = parse_sbi_tsv(text)
        self.assertEqual(acct, "00000020161325222")
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0].deposit, Decimal("40000.00"))
        self.assertEqual(rows[1].withdrawal, Decimal("200.00"))

    def test_fy_prefers_statement_year(self):
        self.assertEqual(ansif_books._fy_end(__import__("datetime").date(2024, 4, 1)), 2025)
        self.assertEqual(ansif_books._fy_end(__import__("datetime").date(2025, 3, 31)), 2025)
        start, end = ansif_books._fy_bounds(2025)
        self.assertEqual(str(start), "2024-04-01")
        self.assertEqual(str(end), "2025-03-31")

    def test_compliance_modules(self):
        data = ansif_books.load_compliance()
        keys = [m["key"] for m in data["modules"]]
        self.assertIn("ITR", keys)
        self.assertIn("GST", keys)
        self.assertIn("TDS", keys)


if __name__ == "__main__":
    unittest.main()
