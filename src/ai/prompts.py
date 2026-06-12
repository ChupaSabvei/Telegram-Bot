PROMPT_VERSION = "v1"

SYSTEM_PROMPT = (
    "Ты помощник по подбору офлайн-мероприятий в России. "
    "Возвращай только JSON-объект со списком event_ids и флагом clarification_needed."
)


def build_user_prompt(query: str, candidates_json: str) -> str:
    return (
        "Запрос пользователя:\n"
        f"{query}\n\n"
        "Кандидаты (JSON):\n"
        f"{candidates_json}\n\n"
        "Выбери максимум 10 наиболее релевантных event_ids."
    )
