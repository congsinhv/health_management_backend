"""
AI-powered workout plan generation using OpenAI.
"""

import json
import logging
from typing import Dict, Any, List

from openai import AsyncOpenAI

from app.config import settings

logger = logging.getLogger(__name__)


async def generate_weekly_plan(
    goal: str,
    weight_kg: float,
    target_weight_kg: float,
    height_m: float,
    selected_days: List[str],
    schedule_mode: str,
    fixed_start_time: str = None,
    fixed_end_time: str = None,
    flexible_periods: Dict = None,
    sports: List[str] = None,
    health_warnings: str = None,
) -> Dict[str, Any]:
    """Generate personalized weekly workout plan via OpenAI."""

    # Build time info
    time_info = []
    for day in selected_days:
        if schedule_mode == "fixed":
            duration = _calculate_duration(fixed_start_time, fixed_end_time)
            time_info.append(f"{day}: {duration} min")
        else:
            periods = flexible_periods.get(day, [])
            if periods:
                p = periods[0]
                duration = _calculate_duration(p["startTime"], p["endTime"])
                time_info.append(
                    f"{day}: {duration} min ({p['startTime']}-{p['endTime']})"
                )

    prompt = f"""Generate a weekly workout plan in Vietnamese:
- Goal: {goal} weight
- Current: {weight_kg}kg, Target: {target_weight_kg or 'maintain'}kg
- Height: {height_m}m
- Schedule: {'; '.join(time_info)}
- Preferred sports: {', '.join(sports or ['general fitness'])}
- Health warnings: {health_warnings or 'None'}

Return JSON format:
{{
    "monday": {{
        "exercise": "Gym - Upper Body",
        "duration_minutes": 60,
        "estimated_calories": 350,
        "description": "Chest press, shoulder press, bicep curls"
    }}
}}

ONLY include days: {selected_days}
Keep descriptions in Vietnamese. Be specific about exercises.
"""

    try:
        client = AsyncOpenAI(api_key=settings.openai_api_key)
        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            temperature=0.7,
            max_tokens=1000,
        )

        plan = json.loads(response.choices[0].message.content)
        logger.info(f"Generated weekly plan for {len(selected_days)} days")
        return plan

    except Exception as e:
        logger.error(f"Failed to generate weekly plan: {e}")
        # Return fallback plan
        return _generate_fallback_plan(selected_days, sports)


def _calculate_duration(start: str, end: str) -> int:
    """Calculate duration in minutes."""
    from datetime import datetime

    if not start or not end:
        return 60

    fmt = "%H:%M:%S" if len(str(start)) > 5 else "%H:%M"
    try:
        s = datetime.strptime(str(start), fmt)
        e = datetime.strptime(str(end), fmt)
        delta = e - s
        return int(delta.total_seconds() / 60)
    except Exception:
        return 60


def _generate_fallback_plan(days: List[str], sports: List[str]) -> Dict:
    """Generate basic fallback plan if AI fails."""
    sport = sports[0] if sports else "General workout"
    return {
        day: {
            "exercise": sport,
            "duration_minutes": 60,
            "estimated_calories": 300,
            "description": "Moderate intensity workout",
        }
        for day in days
    }
