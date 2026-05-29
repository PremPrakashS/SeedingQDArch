import logging
import os
import sqlite3
from datetime import datetime

import pandas as pd

from classify.taxonomy import ISIC_REV5

log = logging.getLogger("classify.reporter")


class ClassificationReporter:
    def __init__(self, db_path: str, output_dir: str):
        self.db_path = db_path
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)

    def generate_all(self, run_timestamp: str | None = None) -> dict[str, str]:
        ts = run_timestamp or datetime.now().strftime("%Y%m%d_%H%M%S")
        paths = {}
        try:
            paths["excel"] = self.generate_excel(ts)
        except Exception as exc:
            log.error("Excel generation failed: %s", exc, exc_info=True)
        try:
            paths["pdf"] = self.generate_pdf(ts)
        except Exception as exc:
            log.error("PDF generation failed: %s", exc, exc_info=True)
        try:
            paths["review_csv"] = self.generate_review_csv(ts)
        except Exception as exc:
            log.error("Review CSV generation failed: %s", exc, exc_info=True)
        return paths

    # ── Excel ─────────────────────────────────────────────────────────────────

    def generate_excel(self, timestamp: str) -> str:
        from openpyxl import Workbook
        from openpyxl.utils.dataframe import dataframe_to_rows

        path = os.path.join(self.output_dir, f"qda_classification_{timestamp}.xlsx")
        wb = Workbook()
        wb.remove(wb.active)

        with sqlite3.connect(self.db_path) as conn:
            projects_df = pd.read_sql_query(
                """
                SELECT p.id, p.title, p.type, p.class,
                       c.isic_section, c.isic_section_title,
                       c.isic_division, c.isic_division_title,
                       c.section_confidence, c.division_confidence,
                       c.classification_status, c.summary, c.flags,
                       c.classified_at, p.project_url, p.doi
                FROM projects p
                LEFT JOIN classifications c ON p.id = c.project_id
                ORDER BY p.id
                """,
                conn,
            )

            files_df = pd.read_sql_query(
                """
                SELECT f.id, f.project_id, p.title AS project_title,
                       f.file_name, f.file_type, f.class, f.status
                FROM files f
                JOIN projects p ON f.project_id = p.id
                ORDER BY f.project_id, f.file_name
                """,
                conn,
            )

            classified = projects_df[projects_df["isic_section"].notna()].copy()

        def write_sheet(name: str, df: pd.DataFrame) -> None:
            ws = wb.create_sheet(name[:31])
            for row in dataframe_to_rows(df, index=False, header=True):
                ws.append(row)

        write_sheet("Projects", projects_df)
        write_sheet("Files", files_df)

        if not classified.empty:
            sec_stats = (
                classified.groupby("isic_section")
                .agg(count=("id", "count"), section_title=("isic_section_title", "first"))
                .reset_index()
                .sort_values("count", ascending=False)
            )
            write_sheet("Stats_by_Section", sec_stats)

            div_stats = (
                classified.groupby(["isic_section", "isic_division"])
                .agg(
                    count=("id", "count"),
                    section_title=("isic_section_title", "first"),
                    division_title=("isic_division_title", "first"),
                )
                .reset_index()
                .sort_values("count", ascending=False)
            )
            write_sheet("Stats_by_Division", div_stats)
        else:
            write_sheet("Stats_by_Section", pd.DataFrame())
            write_sheet("Stats_by_Division", pd.DataFrame())

        flagged = projects_df[
            projects_df["classification_status"].isin(["NEEDS_REVIEW", "AMBIGUOUS"])
            | projects_df["flags"].str.contains("flagged_qda", na=False)
            | projects_df["classification_status"].isin(["INSUFFICIENT_DATA"])
        ].copy()
        write_sheet("Flagged_Review", flagged)

        # Histogram tab
        try:
            hist_path = self._build_histogram(classified, timestamp)
            if hist_path:
                from openpyxl.drawing.image import Image as XLImage
                ws_hist = wb.create_sheet("Histogram")
                ws_hist["A1"] = "Classification distribution"
                img = XLImage(hist_path)
                img.width, img.height = 900, 640
                ws_hist.add_image(img, "A3")
        except Exception as exc:
            log.warning("Histogram embedding failed: %s", exc)

        wb.save(path)
        log.info("Excel report saved: %s", path)
        return path

    # ── PDF ───────────────────────────────────────────────────────────────────

    def generate_pdf(self, timestamp: str) -> str:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import cm
        from reportlab.platypus import (
            Image, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle,
        )

        path = os.path.join(self.output_dir, f"qda_classification_{timestamp}.pdf")

        with sqlite3.connect(self.db_path) as conn:
            total = pd.read_sql_query("SELECT COUNT(*) AS n FROM projects", conn).iloc[0]["n"]
            classified_n = pd.read_sql_query(
                "SELECT COUNT(*) AS n FROM classifications WHERE isic_section IS NOT NULL", conn
            ).iloc[0]["n"]
            status_df = pd.read_sql_query(
                "SELECT classification_status, COUNT(*) AS n FROM classifications GROUP BY classification_status",
                conn,
            )
            sec_df = pd.read_sql_query(
                """SELECT isic_section, isic_section_title, COUNT(*) AS n
                   FROM classifications WHERE isic_section IS NOT NULL
                   GROUP BY isic_section ORDER BY n DESC""",
                conn,
            )

        styles = getSampleStyleSheet()
        H = ParagraphStyle("H", parent=styles["Heading1"], fontSize=16, spaceAfter=12)
        H2 = ParagraphStyle("H2", parent=styles["Heading2"], fontSize=12, spaceAfter=8)

        doc = SimpleDocTemplate(
            path, pagesize=A4,
            rightMargin=2 * cm, leftMargin=2 * cm,
            topMargin=2 * cm, bottomMargin=2 * cm,
        )

        story = [
            Paragraph("QDA Classification Report", H),
            Paragraph(
                f"Generated: {datetime.now():%Y-%m-%d %H:%M} | "
                f"Total projects: {total} | Classified: {classified_n}",
                styles["Normal"],
            ),
            Spacer(1, 0.5 * cm),
            Paragraph("Summary", H2),
        ]

        summary_data = [["Metric", "Value"]] + [
            [row["classification_status"], str(row["n"])]
            for _, row in status_df.iterrows()
        ]
        t = Table(summary_data, colWidths=[8 * cm, 5 * cm])
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
            ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
            ("FONTSIZE", (0, 0), (-1, -1), 10),
        ]))
        story.append(t)
        story.append(Spacer(1, 0.5 * cm))

        if not sec_df.empty:
            story.append(Paragraph("ISIC Section Distribution", H2))
            sec_data = [["Section", "Title", "Count"]] + [
                [row["isic_section"], (row["isic_section_title"] or "")[:55], str(row["n"])]
                for _, row in sec_df.iterrows()
            ]
            t2 = Table(sec_data, colWidths=[2 * cm, 11 * cm, 2 * cm])
            t2.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.lightgreen),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
            ]))
            story.append(t2)

        # Histogram page
        with sqlite3.connect(self.db_path) as conn:
            cl_df = pd.read_sql_query(
                "SELECT isic_section, isic_division FROM classifications WHERE isic_section IS NOT NULL",
                conn,
            )
        hist_path = self._build_histogram(cl_df, timestamp)
        if hist_path:
            story += [
                PageBreak(),
                Paragraph("Distribution Histograms", H2),
                Image(hist_path, width=17 * cm, height=12 * cm),
            ]

        doc.build(story)
        log.info("PDF report saved: %s", path)
        return path

    # ── Review CSV ────────────────────────────────────────────────────────────

    def generate_review_csv(self, timestamp: str) -> str:
        path = os.path.join(self.output_dir, f"review_queue_{timestamp}.csv")
        with sqlite3.connect(self.db_path) as conn:
            df = pd.read_sql_query(
                """
                SELECT p.id, p.title, p.project_url,
                       c.isic_section, c.isic_division,
                       c.section_confidence, c.division_confidence,
                       c.classification_status, c.summary, c.flags
                FROM projects p
                LEFT JOIN classifications c ON p.id = c.project_id
                WHERE c.classification_status IN ('NEEDS_REVIEW','AMBIGUOUS','INSUFFICIENT_DATA')
                   OR c.flags LIKE '%flagged_qda%'
                   OR (c.id IS NULL)
                ORDER BY p.id
                """,
                conn,
            )
        df.to_csv(path, index=False)
        log.info("Review queue saved: %s (%d rows)", path, len(df))
        return path

    # ── Histogram helper ──────────────────────────────────────────────────────

    def _build_histogram(self, df: pd.DataFrame, timestamp: str) -> str | None:
        try:
            import matplotlib
            matplotlib.use("Agg")
            import matplotlib.pyplot as plt

            fig, axes = plt.subplots(1, 2, figsize=(14, 5))

            ax = axes[0]
            if not df.empty and "isic_section" in df.columns:
                counts = df["isic_section"].value_counts().sort_index()
                counts.plot(kind="bar", ax=ax, color="steelblue")
            ax.set_title("Projects per ISIC Section")
            ax.set_xlabel("Section")
            ax.set_ylabel("Count")
            ax.tick_params(axis="x", rotation=0)

            ax = axes[1]
            if not df.empty and "isic_section" in df.columns and "isic_division" in df.columns:
                df = df.copy()
                df["sec_div"] = df["isic_section"].fillna("?") + "/" + df["isic_division"].fillna("?")
                top15 = df["sec_div"].value_counts().head(15)
                top15.plot(kind="barh", ax=ax, color="indianred")
            ax.set_title("Top ISIC Divisions")
            ax.set_xlabel("Count")

            plt.tight_layout()
            hist_path = os.path.join(self.output_dir, f"histogram_{timestamp}.png")
            plt.savefig(hist_path, dpi=150, bbox_inches="tight")
            plt.close(fig)
            return hist_path
        except Exception as exc:
            log.warning("Histogram creation failed: %s", exc)
            return None
