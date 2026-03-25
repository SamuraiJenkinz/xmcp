"""Start the Atlas chat application with HTTPS."""

import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)

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
