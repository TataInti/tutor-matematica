from pathlib import Path
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.curriculum import find_unit_path, load_unit


router = APIRouter()
templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent / "templates"))
UNIT_FILENAME = "probabilidad_condicional.yml"
SESSION_PATH = "/sesion/probabilidad-condicional"


def _page_context(request: Request, unit: dict[str, Any], **extra: Any) -> dict[str, Any]:
    return {"request": request, "unidad": unit, **extra}


def _load_unit() -> dict[str, Any]:
    return load_unit(find_unit_path(UNIT_FILENAME))


@router.get(SESSION_PATH, response_class=HTMLResponse)
def show_session(request: Request) -> HTMLResponse:
    unit = _load_unit()
    return templates.TemplateResponse(
        request=request,
        name="sesion.html",
        context=_page_context(request, unit, respuestas={}, resultados=None),
    )


@router.post(SESSION_PATH, response_class=HTMLResponse)
async def answer_quiz(request: Request) -> HTMLResponse:
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
