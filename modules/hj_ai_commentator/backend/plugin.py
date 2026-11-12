"""JACK AI v0.1 development preview; no AI or broadcast."""
from fastapi import Depends, HTTPException, Request
from pydantic import BaseModel, Field
from .preview import build_preview

class PreviewRequest(BaseModel):
    event_type: str = Field(max_length=80)
    payload: dict = Field(default_factory=dict)
    confirmed: bool = False

class Plugin:
    def self_check(self):
        return build_preview("seat.changed", {}, True)["mode"] == "offline_template"

    def register(self, app, ctx, folder):
        @app.get("/api/jack-ai/status")
        async def status(request: Request):
            await ctx.admin_only(request)
            return {"module": "hj.ai_commentator", "mode": "offline_preview_only",
                    "llm_connected": False, "voice_enabled": False,
                    "obs_output_enabled": False, "training_sync_enabled": False}

        @app.post("/api/jack-ai/preview", dependencies=[Depends(ctx.admin_only)])
        async def preview(body: PreviewRequest):
            try:
                return build_preview(body.event_type, body.payload, body.confirmed)
            except ValueError as exc:
                raise HTTPException(422, detail=str(exc)) from exc

def create_plugin():
    return Plugin()
