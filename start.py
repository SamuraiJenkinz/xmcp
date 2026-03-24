"""Start the Atlas chat application with HTTPS."""

from dotenv import load_dotenv

load_dotenv()

from chat_app.app import create_app

app = create_app()
app.run(
    host="0.0.0.0",
    port=5050,
    ssl_context=(
        "usdf11v1784.mercer.com-chaincert-combined.crt",
        "usdf11v1784.mercer.com-private.key",
    ),
)
