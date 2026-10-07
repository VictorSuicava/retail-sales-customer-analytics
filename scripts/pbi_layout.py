"""Reusable PBIR layout helpers for standard Power BI visuals."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "powerbi/Retail.Report"
SCHEMA = "https://developer.microsoft.com/json-schemas/fabric/item/report/"

def write_json(path: Path, content: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(content, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def identifier(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()[:20]


def literal(value) -> dict:
    if isinstance(value, bool):
        text = "true" if value else "false"
    elif isinstance(value, (int, float)):
        text = f"{value}D"
    else:
        text = "'" + str(value).replace("'", "''") + "'"
    return {"expr": {"Literal": {"Value": text}}}


def colour(value: str) -> dict:
    return {"solid": {"color": literal(value)}}


def column(table: str, name: str, label: str | None = None) -> dict:
    return {"field": {"Column": {"Expression": {"SourceRef": {"Entity": table}}, "Property": name}},
            "queryRef": f"{table}.{name}", "nativeQueryRef": label or name,
            "displayName": label or name}


def measure(name: str, label: str | None = None) -> dict:
    return {"field": {"Measure": {"Expression": {"SourceRef": {"Entity": "Metrics"}}, "Property": name}},
            "queryRef": f"Metrics.{name}", "nativeQueryRef": name,
            "displayName": label or name}


def selection_filter(table: str, field: str, value: str) -> dict:
    return {"filter": {"Version": 2, "From": [{"Name": "s", "Entity": table, "Type": 0}],
        "Where": [{"Condition": {"In": {
            "Expressions": [{"Column": {"Expression": {"SourceRef": {"Source": "s"}}, "Property": field}}],
            "Values": [[{"Literal": {"Value": "'" + value.replace("'", "''") + "'"}}]]
        }}}]}}


def formatting(title: str, background: str = "#FFFFFF", border: bool = True) -> dict:
    return {
        "title": [{"properties": {"show": literal(bool(title)), "text": literal(title),
                    "fontSize": literal(12), "fontColor": colour("#182230"), "bold": literal(True)}}],
        "background": [{"properties": {"show": literal(True), "color": colour(background), "transparency": literal(0)}}],
        "border": [{"properties": {"show": literal(border), "color": colour("#E4E9F0"), "radius": literal(8)}}],
    }


class Page:
    def __init__(self, name: str, display_name: str):
        self.name = identifier(name)
        self.path = REPORT / "definition/pages" / self.name
        self.number = 0
        write_json(self.path / "page.json", {
            "$schema": SCHEMA + "definition/page/2.1.0/schema.json",
            "name": self.name, "displayName": display_name, "displayOption": "FitToPage",
            "height": 720, "width": 1280,
            "objects": {"background": [{"properties": {"color": colour("#F7F9FC"), "transparency": literal(0)}}]},
        })

    def visual(self, kind: str, title: str, bounds: tuple, roles: dict | None = None,
               objects: dict | None = None, sort: dict | None = None) -> None:
        self.number += 1
        visual_name = identifier(f"{self.name}:{self.number}")
        x, y, width, height = bounds
        config = {"visualType": kind, "drillFilterOtherVisuals": True,
                  "visualContainerObjects": formatting(title)}
        if kind == "textbox":
            config["visualContainerObjects"] = {
                "title": [{"properties": {"show": literal(False)}}],
                "background": [{"properties": {"show": literal(False)}}],
                "border": [{"properties": {"show": literal(False)}}],
                "padding": [{"properties": {side: literal(0) for side in ("top", "bottom", "left", "right")}}],
            }
        if roles:
            query = {"queryState": {role: {"projections": projections} for role, projections in roles.items()}}
            if sort:
                query["sortDefinition"] = {"sort": [sort], "isDefaultSort": False}
            config["query"] = query
        if objects:
            config["objects"] = objects
        if kind == "lineChart":
            config.setdefault("objects", {}).setdefault("valueAxis", [{"properties": {
                "showAxisTitle": literal(False)}}])
        if kind == "barChart":
            config.setdefault("objects", {}).setdefault("categoryAxis", [{"properties": {
                "preferredCategoryWidth": literal(14), "fontSize": literal(9),
                "innerPadding": literal(20)}}])
        if kind == "tableEx":
            config.setdefault("objects", {}).update({
                "grid": [{"properties": {"rowPadding": literal(1)}}],
                "values": [{"properties": {"fontSize": literal(11)}}],
                "columnHeaders": [{"properties": {"fontSize": literal(11), "wordWrap": literal(False)}}],
                "total": [{"properties": {"fontSize": literal(11)}}],
            })
        write_json(self.path / "visuals" / visual_name / "visual.json", {
            "$schema": SCHEMA + "definition/visualContainer/2.7.0/schema.json",
            "name": visual_name,
            "position": {"x": x, "y": y, "z": self.number, "height": height, "width": width,
                         "tabOrder": self.number},
            "visual": config,
        })

    def text(self, text: str, bounds: tuple, size: int = 12, bold: bool = False) -> None:
        self.visual("textbox", "", bounds, objects={"general": [{"properties": {
            "paragraphs": [{"textRuns": [{"value": text, "textStyle": {
                "fontFamily": "Segoe UI", "fontSize": f"{size}pt", "fontWeight": "bold" if bold else "normal",
                "color": "#182230"}}]}]}}]})

    def slicer(self, table: str, field: str, title: str, bounds: tuple, selected: str | None = None) -> None:
        props = {"mode": literal("Dropdown")}
        objects = {"data": [{"properties": props}], "header": [{"properties": {"show": literal(False)}}], "selection": [{"properties": {
            "singleSelect": literal(True), "selectAllCheckboxEnabled": literal(False)}}]}
        if selected:
            objects["general"] = [{"properties": {"filter": selection_filter(table, field, selected)}}]
        self.visual("slicer", title, bounds, {"Values": [column(table, field, title)]}, objects)

    def card(self, metric: str, bounds: tuple, title: str | None = None) -> None:
        self.visual("card", title or metric, bounds, {"Values": [measure(metric)]}, {
            "labels": [{"properties": {"fontSize": literal(30), "color": colour("#136F63"), "labelDisplayUnits": literal(1)}}],
            "categoryLabels": [{"properties": {"show": literal(False)}}],
        })


