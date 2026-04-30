from datetime import datetime, timedelta, timezone

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Event, Subscriber


class EventRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_source_url(self, url: str) -> Event | None:
        result = await self.session.execute(
            select(Event).where(Event.source_url == url)
        )
        return result.scalar_one_or_none()

    async def create(self, **kwargs) -> Event:
        event = Event(**kwargs)
        self.session.add(event)
        await self.session.commit()
        await self.session.refresh(event)
        return event

    async def mark_notified_advance(self, event_id: int) -> None:
        await self.session.execute(
            update(Event).where(Event.id == event_id).values(notified_advance=True)
        )
        await self.session.commit()

    async def mark_notified_today(self, event_id: int) -> None:
        await self.session.execute(
            update(Event).where(Event.id == event_id).values(notified_today=True)
        )
        await self.session.commit()

    async def get_pending_advance_notifications(self) -> list[Event]:
        """Return events not yet advance-notified (saved by local parser)."""
        result = await self.session.execute(
            select(Event).where(Event.notified_advance.is_(False))
        )
        return list(result.scalars().all())

    async def get_pending_today_notifications(self, notify_before_minutes: int) -> list[Event]:
        """Return events whose sale opens within the next notify_before_minutes and haven't been notified yet."""
        now = datetime.now(timezone.utc)
        window_end = now + timedelta(minutes=notify_before_minutes)
        result = await self.session.execute(
            select(Event).where(
                Event.notified_today.is_(False),
                Event.notified_advance.is_(True),
                Event.sale_opens_at.is_not(None),
                Event.sale_opens_at >= now,
                Event.sale_opens_at <= window_end,
            )
        )
        return list(result.scalars().all())

    async def get_upcoming(self, limit: int = 10) -> list[Event]:
        now = datetime.now(timezone.utc)
        result = await self.session.execute(
            select(Event)
            .where(Event.sale_opens_at >= now)
            .order_by(Event.sale_opens_at)
            .limit(limit)
        )
        return list(result.scalars().all())


class SubscriberRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, user_id: int) -> Subscriber | None:
        result = await self.session.execute(
            select(Subscriber).where(Subscriber.max_user_id == user_id)
        )
        return result.scalar_one_or_none()

    async def subscribe(self, user_id: int) -> tuple[Subscriber, bool]:
        """Return (subscriber, is_new)."""
        sub = await self.get(user_id)
        if sub:
            was_active = sub.active
            sub.active = True
            await self.session.commit()
            return sub, not was_active
        sub = Subscriber(max_user_id=user_id, active=True)
        self.session.add(sub)
        await self.session.commit()
        return sub, True

    async def unsubscribe(self, user_id: int) -> bool:
        sub = await self.get(user_id)
        if not sub or not sub.active:
            return False
        sub.active = False
        await self.session.commit()
        return True

    async def get_active(self) -> list[Subscriber]:
        result = await self.session.execute(
            select(Subscriber).where(Subscriber.active.is_(True))
        )
        return list(result.scalars().all())
