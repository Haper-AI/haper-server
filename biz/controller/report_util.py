from haper_script.schema_gen.python import report as report_model


def initialize_report(messages_in_queue=None):
    if messages_in_queue is None:
        messages_in_queue = {}
    return report_model.Report(
        messages_in_queue=messages_in_queue,
        summary=[],
        content=report_model.ReportContent(
            content_sources=[],
            gmail=None,
            outlook=None
        ),
    )
