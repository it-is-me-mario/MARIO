"""Shared content for the project resource pages."""

# The course form opens a draft in the visitor's email application.
TEACHING_CLOSING = {
    "text": "Request a <mark>MARIO course</mark>",
    "dialog": {
        "title": "MARIO courses",
        "intro": (
            "We don't run scheduled courses yet, but if you or your team are interested "
            "in a course, we can work out the format together."
        ),
        "subject": "MARIO course enquiry",
        # Split so no address appears whole in the page source.
        "recipients": [("lorenzo.rinaldi", "polimi.it"), ("nicolo.golinucci", "enextgen.it")],
    },
}
