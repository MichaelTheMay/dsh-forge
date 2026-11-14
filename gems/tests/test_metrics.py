import unittest

from gems.eval.metrics import pairwise_agreement, precision_at_k, spearman, top_share_lift


class MetricsTests(unittest.TestCase):
    def test_precision_counts_only_labelled_items_in_the_top_k(self):
        ranked = ["a", "b", "c", "d"]
        labels = {"a": True, "c": False, "d": True}
        self.assertEqual(precision_at_k(ranked, labels, 3), (0.5, 2))
        self.assertEqual(precision_at_k(ranked, labels, 4), (0.667, 3))
        self.assertEqual(precision_at_k(ranked, {}, 3), (None, 0))

    def test_pairwise_agreement(self):
        labels = {"good1": True, "good2": True, "bad1": False}
        self.assertEqual(pairwise_agreement({"good1": 9, "good2": 8, "bad1": 1}, labels), 1.0)
        self.assertEqual(pairwise_agreement({"good1": 1, "good2": 1, "bad1": 9}, labels), 0.0)
        self.assertEqual(pairwise_agreement({"good1": 5, "good2": 5, "bad1": 5}, labels), 0.5)
        # A good project left out of the ranking counts as ranked last.
        self.assertEqual(pairwise_agreement({"good1": 9, "bad1": 5}, labels), 0.5)
        self.assertIsNone(pairwise_agreement({"good1": 1}, {"good1": True}))

    def test_spearman(self):
        self.assertEqual(spearman([1, 2, 3, 4], [10, 20, 30, 40]), 1.0)
        self.assertEqual(spearman([1, 2, 3, 4], [4, 3, 2, 1]), -1.0)
        self.assertIsNone(spearman([1, 1, 1], [1, 2, 3]))
        self.assertIsNone(spearman([1, 2], [1, 2]))

    def test_top_share_lift(self):
        scores = [9, 8, 1, 1, 1, 1, 1, 1, 1, 1]
        outcomes = [10, 10, 0, 0, 0, 0, 0, 0, 0, 0]
        self.assertEqual(top_share_lift(scores, outcomes, 0.2), 5.0)
        self.assertEqual(top_share_lift(scores[::-1], outcomes, 0.2), 0.0)
        self.assertIsNone(top_share_lift([1, 2], [1, 2]))
        self.assertIsNone(top_share_lift([1] * 6, [0] * 6))


if __name__ == "__main__":
    unittest.main()
