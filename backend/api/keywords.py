import json
import os

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter()

_KEYWORDS_FILE = os.path.join(
    os.path.dirname(__file__), '..', '..', 'lender_keywords.json'
)


def _load():
    if not os.path.exists(_KEYWORDS_FILE):
        return []
    try:
        with open(_KEYWORDS_FILE, 'r') as f:
            return json.load(f)
    except Exception:
        return []


def _save(keywords):
    with open(_KEYWORDS_FILE, 'w') as f:
        json.dump(keywords, f, indent=2)


class KeywordBody(BaseModel):
    name: str
    type: str = 'debit'


@router.get('/lender-keywords')
def get_keywords():
    return _load()


@router.post('/lender-keywords')
def add_keyword(body: KeywordBody):
    name = body.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail='name is required')
    keywords = _load()
    if not any(k['name'].lower() == name.lower() and k['type'] == body.type for k in keywords):
        keywords.append({'name': name, 'type': body.type})
        _save(keywords)
    return keywords


@router.delete('/lender-keywords')
def remove_keyword(body: KeywordBody):
    keywords = _load()
    keywords = [
        k for k in keywords
        if not (k['name'].lower() == body.name.lower() and k['type'] == body.type)
    ]
    _save(keywords)
    return keywords
