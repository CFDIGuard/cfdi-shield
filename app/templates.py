from fastapi.templating import Jinja2Templates

from app.core.csrf import csrf_context_processor
from app.resource_paths import resource_path


templates = Jinja2Templates(
    directory=str(resource_path("templates")),
    context_processors=[csrf_context_processor],
)
