from checks.base import BaseCheck


class SchemaChangeCheck(BaseCheck):
    name = "schema_change"
    alert_type = "schema"

    def run(self, current, history):
        if not history:
            return []

        previous_columns = set(history[0]["columns"])
        current_columns = set(current["columns"])
        removed = previous_columns - current_columns
        added = current_columns - previous_columns

        alerts = []
        if removed:
            alerts.append({
                "type": self.alert_type,
                "level": "error",
                "text": f"Columns REMOVED: {removed}",
            })
        if added:
            alerts.append({
                "type": self.alert_type,
                "level": "warning",
                "text": f"Columns ADDED: {added}",
            })
        return alerts
