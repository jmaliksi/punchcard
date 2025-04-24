import calendar
import itertools
import json
import secrets
import sqlite3
import os
import uuid
from contextlib import contextmanager
from datetime import date
from fastapi import Depends, FastAPI, Request, HTTPException, status
from fastapi.responses import HTMLResponse, PlainTextResponse, RedirectResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from typing import Annotated, Optional


DATABASE = 'data/db.db'

app = FastAPI(
    title='Punchcard',
    version='0.0.1',
    openapi_url=None,
    docs_url=None,
    redoc_url=None,
)
security = HTTPBasic()

limiter = Limiter(
    key_func=get_remote_address,
    default_limits=['1/second'],
)
app.state.limiter = limiter
app.add_exception_handler(429, _rate_limit_exceeded_handler)

templates = Jinja2Templates(directory="templates")


@contextmanager
def db():
    con = sqlite3.connect(DATABASE)
    con.row_factory = sqlite3.Row
    try:
        yield con
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()


def bootstrap_db():
    with db() as conn:
        conn.execute('CREATE TABLE punchcards (id TEXT PRIMARY KEY, year INTEGER NOT NULL, label TEXT, punches TEXT)')


class Punchcard:
    def __init__(self, year: int, label: str = ''):
        self._id = uuid.uuid4()
        self._year = year
        self._label = label
        self._punched = set()

    @classmethod
    def load_json(cls, data: [dict, str]) -> 'Punchcard':
        if isinstance(data, str):
            data = json.loads(data)
        punchcard = Punchcard(data['year'], data['label'])
        punchcard._id = data['id']
        punchcard._punched = {(m, d) for m, d in data['punches']}
        return punchcard

    @classmethod
    def get_db(cls, id: str) -> 'Punchcard':
        with db() as conn:
            row = conn.execute('SELECT * FROM punchcards WHERE id = ?', (id, )).fetchone()
            return cls.load_json(row['punches'])

    def punch(self, month: int, day: int, punch=True) -> bool:
        if month <= 0 or month > 12:
            raise IndexError(f'month {month} out of range')
        if day <= 0 or day > calendar.monthrange(self._year, month)[1]:
            raise IndexError(f'day {day} out of range for month {month}')
        if punch:
            self._punched.add((month, day))
        else:
            if (month, day) in self._punched:
                self._punched.remove((month, day))
        return punch

    def punchgrid(self):
        grid = [['jan', 'feb', 'mar', 'apr', 'may', 'jun', 'jul', 'aug', 'sep', 'oct', 'nov', 'dec']]
        for date in range(1, 32):
            row = []
            for month in range(1, 13):
                if date <= calendar.monthrange(self._year, month)[1]:
                    row.append((date, (month, date) in self._punched))
                else:
                    row.append((-1, False))
            grid.append(row)
        return grid

    def to_json(self) -> dict:
        return {
            'id': str(self._id),
            'year': self._year,
            'label': self._label,
            'punches': list(self._punched),
        }

    def save(self):
        with db() as conn:
            punches = json.dumps(self.to_json())
            conn.execute('INSERT INTO punchcards (id, year, label, punches) VALUES (?, ?, ?, ?) ON CONFLICT (id) DO UPDATE SET label=?, punches=?;', (
                str(self._id),
                self._year,
                self._label,
                punches,
                self._label,
                punches,
            ))

    def to_template_var(self) -> dict:
        return {
            'id': self._id,
            'year': self._year,
            'punches': self.punchgrid(),
            'label': self._label,
        }


def auth(credentials: Annotated[HTTPBasicCredentials, Depends(security)]):
    u = os.environ.get('PUNCHCARD_USERNAME')
    p = os.environ.get('PUNCHCARD_PASSWORD')
    if not u and not p:
        return True
    username_good = secrets.compare_digest(credentials.username, u)
    pw_good = secrets.compare_digest(credentials.password, p)
    if not (username_good and pw_good):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="bluh",
            headers={"WWW-Authenticate": "Basic"},
        )
    return True


@app.get('/')
async def index():
    return RedirectResponse(url='/punchcard', status_code=302)


@app.get('/punchcard', response_class=HTMLResponse)
async def get_punchcard(request: Request, authed: Annotated[bool, Depends(auth)], year: int = -1):
    context = {
        "year": year,
        "years": [],
        "punchcards": [],
        "today": {
            "month": date.today().month,
            "date": date.today().day,
        },
    }
    with db() as conn:
        context['years'] = [row['year'] for row in conn.execute('SELECT distinct(year) FROM punchcards ORDER BY year DESC')]
        if year == -1 and context['years']:
            year = context['years'][0]
        context['punchcards'] = [Punchcard.load_json(row['punches']).to_template_var() for row in conn.execute('SELECT * FROM punchcards WHERE year=? ORDER BY label', (year,))]
    return templates.TemplateResponse(
        request=request,
        name='punchcard.html',
        context=context,
    )


class PunchBody(BaseModel):
    month: int
    day: int
    punch: bool


@app.put('/punchcard/{id}/punch')
@limiter.limit("10/second")
async def punch_punchcard(request: Request, id: str, punch: PunchBody, authed: Annotated[bool, Depends(auth)]):
    punchcard = Punchcard.get_db(id)
    punchcard.punch(punch.month, punch.day, punch.punch)
    punchcard.save()
    return {'ok': True}


class NewPunchcard(BaseModel):
    year: int
    label: str


@app.post('/punchcard')
async def create_punchcard(punchcard: NewPunchcard, authed: Annotated[bool, Depends(auth)]):
    pc = Punchcard(punchcard.year, punchcard.label)
    pc.save()
    return {'ok': True}


@app.delete('/punchcard/{id}')
async def delete_punchcard(id: str, authed: Annotated[bool, Depends(auth)]):
    with db() as conn:
        conn.execute('DELETE FROM punchcards WHERE id=?', (id, ))
    return {'ok': True}


class UpdatePunchcard(BaseModel):
    year: Optional[int] = None
    label: Optional[str] = None


@app.put('/punchcard/{id}')
async def update_punchcard(id: str, authed: Annotated[bool, Depends(auth)], update: UpdatePunchcard):
    # crud more like piece of crud amirite
    pc = Punchcard.get_db(id)
    if update.year is not None:
        pc._year = update.year
    if update.label is not None:
        pc._label = update.label
    pc.save()
    return {'ok': True}


@app.get('/robots.txt', response_class=PlainTextResponse)
def robots():
    return "User-agent: *\nDisallow: /"


if __name__ == "__main__":
    try:
        bootstrap_db()
    except Exception as e:
        print(e)
