from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates

from app.curriculum import find_unit_path, load_unit
from app.db import get_database_path, get_known_item_ids, mark_item_known


router = APIRouter()
templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent / "templates"))
UNIT_FILENAME = "probabilidad_condicional.yml"
DIAGNOSTIC_FILENAME = "algebra_diagnostico.yml"
DIAGNOSTIC_UNIT_ID = "algebra_diagnostico"
SESSION_PATH = "/sesion/probabilidad-condicional"
DIAGNOSTIC_PATH = "/sesion/algebra-diagnostico"


def _page_context(request: Request, unit: dict[str, Any], **extra: Any) -> dict[str, Any]:
    return {"request": request, "unidad": unit, **extra}


def _load_unit() -> dict[str, Any]:
    return load_unit(find_unit_path(UNIT_FILENAME))


def _load_diagnostic() -> dict[str, Any]:
    return load_unit(find_unit_path(DIAGNOSTIC_FILENAME))


def _diagnostic_is_approved(db_path: Path) -> bool:
    diagnostic = _load_diagnostic()
    required_ids = {item["id"] for item in diagnostic["items_opcion_multiple"]}
    known_ids = get_known_item_ids(diagnostic["id"], db_path)
    return required_ids.issubset(known_ids)


def _first_unsolved_item(
    diagnostic: dict[str, Any], known_ids: set[str]
) -> tuple[int, dict[str, Any]] | None:
    for index, item in enumerate(diagnostic["items_opcion_multiple"]):
        if item["id"] not in known_ids:
            return index, item
    return None


def _render_diagnostic(
    request: Request,
    diagnostic: dict[str, Any],
    item: dict[str, Any],
    index: int,
    *,
    mensaje: str | None = None,
    paso_clave: str | None = None,
) -> HTMLResponse:
    return templates.TemplateResponse(
        request=request,
        name="diagnostico.html",
        context={
            "request": request,
            "titulo": diagnostic["explicacion"]["titulo"],
            "introduccion": diagnostic["explicacion"]["texto"],
            "item": item,
            "numero_item": index + 1,
            "total_items": len(diagnostic["items_opcion_multiple"]),
            "mensaje": mensaje,
            "paso_clave": paso_clave,
        },
    )


@router.get(SESSION_PATH, response_class=HTMLResponse)
def show_session(
    request: Request, db_path: Path = Depends(get_database_path)
) -> Response:
    if not _diagnostic_is_approved(db_path):
        return RedirectResponse(DIAGNOSTIC_PATH, status_code=307)
    unit = _load_unit()
    return templates.TemplateResponse(
        request=request,
        name="sesion.html",
        context=_page_context(request, unit, respuestas={}, resultados=None),
    )


@router.post(SESSION_PATH, response_class=HTMLResponse)
async def answer_quiz(
    request: Request, db_path: Path = Depends(get_database_path)
) -> Response:
    if not _diagnostic_is_approved(db_path):
        return RedirectResponse(DIAGNOSTIC_PATH, status_code=303)
    unit = _load_unit()
    questions = unit["items_opcion_multiple"]
    form = await request.form()
    answers = {
        question["id"]: answer
        for question in questions
        if isinstance((answer := form.get(question["id"])), str)
    }

    results = []
    incorrect_count = 0
    for question in questions:
        answer = answers.get(question["id"])
        correct = answer == question["respuesta_correcta"]
        if answer is not None and not correct:
            incorrect_count += 1
        if answer is None:
            message = "Te falta responder este ítem."
        elif correct:
            message = "Ítem sabido: elegiste la opción correcta."
        else:
            message = "Todavía no: revisá la explicación y volvé a intentarlo."
        results.append(
            {
                "pregunta": question["pregunta"],
                "respondida": answer is not None,
                "correcta": correct,
                "mensaje": message,
                "explicacion": question["explicacion_respuesta"],
            }
        )

    test_complete = len(answers) == len(questions)
    paper_unlocked = test_complete and incorrect_count < 2
    if not test_complete:
        result_message = "Respondé las cinco preguntas para revisar el test."
    elif incorrect_count >= 2:
        result_message = (
            "Tuviste dos o más respuestas incorrectas; todavía no pasás al ejercicio en papel."
        )
    else:
        result_message = "Listo, ya podés seguir al ejercicio en papel."

    return templates.TemplateResponse(
        request=request,
        name="sesion.html",
        context=_page_context(
            request,
            unit,
            respuestas=answers,
            resultados=results,
            mensaje_resultado=result_message,
            errores=incorrect_count,
            papel_habilitado=paper_unlocked,
        ),
    )


@router.get(DIAGNOSTIC_PATH, response_class=HTMLResponse)
def show_diagnostic(
    request: Request, db_path: Path = Depends(get_database_path)
) -> Response:
    diagnostic = _load_diagnostic()
    known_ids = get_known_item_ids(diagnostic["id"], db_path)
    next_item = _first_unsolved_item(diagnostic, known_ids)
    if next_item is None:
        return RedirectResponse(SESSION_PATH, status_code=303)
    index, item = next_item
    return _render_diagnostic(request, diagnostic, item, index)


@router.post(DIAGNOSTIC_PATH, response_class=HTMLResponse)
async def answer_diagnostic(
    request: Request, db_path: Path = Depends(get_database_path)
) -> Response:
    diagnostic = _load_diagnostic()
    known_ids = get_known_item_ids(diagnostic["id"], db_path)
    next_item = _first_unsolved_item(diagnostic, known_ids)
    if next_item is None:
        return RedirectResponse(SESSION_PATH, status_code=303)
    index, item = next_item
    form = await request.form()

    submitted_item_id = form.get("item_id")
    if submitted_item_id is not None and submitted_item_id != item["id"]:
        return _render_diagnostic(
            request,
            diagnostic,
            item,
            index,
            mensaje="La pregunta cambió. Respondé la que aparece ahora.",
        )

    if form.get("respuesta") != item["respuesta_correcta"]:
        return _render_diagnostic(
            request,
            diagnostic,
            item,
            index,
            mensaje="Todavía no quedó sabido. Revisemos el paso clave.",
            paso_clave=item["paso_clave"],
        )

    mark_item_known(item["id"], diagnostic["id"], db_path)
    known_ids = get_known_item_ids(diagnostic["id"], db_path)
    next_item = _first_unsolved_item(diagnostic, known_ids)
    if next_item is None:
        return RedirectResponse(SESSION_PATH, status_code=303)
    next_index, item = next_item
    return _render_diagnostic(
        request,
        diagnostic,
        item,
        next_index,
        mensaje="Bien, este ítem quedó sabido. Seguimos con el siguiente.",
    )
