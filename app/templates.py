from fastapi.templating import Jinja2Templates

from app.resource_paths import resource_path


templates = Jinja2Templates(directory=str(resource_path("templates")))
