# Frontend

Next.js frontend for the live end-to-end pipeline used in `backend/test_onboarding_live.py`:
`start interview -> reply -> complete -> start exploration -> select self -> converse -> branch`.

## Run

1. Start backend API (repo root):
   - `python3 -m uvicorn backend.app:app --reload --host 0.0.0.0 --port 8000`
2. Start frontend (new terminal):
   - `cd frontend`
   - `npm install`
   - `npm run dev`
3. Open:
   - `http://localhost:3000`

If backend runs on another host/port:
- `NEXT_PUBLIC_API_BASE_URL=http://localhost:8000 npm run dev`

## Implemented Flow

- Landing: choose `sessionId` and start interview (`POST /interview/start`)
- Interview chat (`POST /interview/reply`) with status refresh (`GET /interview/status`)
- Complete onboarding (`POST /interview/complete`)
- Auto-start exploration (`POST /pipeline/start-exploration`)
- Future self selection and conversation (`POST /conversation/reply`)
- Re-branch from active self (`POST /pipeline/branch-conversation`)
- Pipeline status refresh (`GET /pipeline/status/{sessionId}`)

## Structure

- `frontend/app/`: Next.js entrypoint and global styles
- `frontend/screens/`: route-level UI states
- `frontend/components/`: reusable presentational components
- `frontend/lib/api.ts`: backend API client + normalization
