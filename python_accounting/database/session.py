# database/session.py
# Copyright (C) 2024 - 2028 the PythonAccounting authors and contributors
# <see AUTHORS file>
#
# This module is part of PythonAccounting and is released under
# the MIT License: https://www.opensource.org/licenses/mit-license.php

"""
Provides accounting specific overrides for some sqlalchemy session methods.

"""
from sqlalchemy.orm import sessionmaker
from sqlalchemy.orm.session import Session

from python_accounting.models import Entity
from python_accounting.database.session_overrides import SessionOverridesMixin
from python_accounting.database.accounting_functions import AccountingFunctionsMixin
from python_accounting.database.event_listeners import EventListenersMixin, register_accounting_events

class AccountingSession(
    SessionOverridesMixin, EventListenersMixin, AccountingFunctionsMixin, Session
):
    """
    Custom methods specific to accounting.

    Attributes:
        entity (Entity): The Entity currently associated with the session. All database
            queries will be scoped to this entity.
    """
    entity: Entity

    def __init__(self, bind=None, info=None, **kwargs) -> None:
        super().__init__(bind=bind, info=info, **kwargs)

def get_session_factory(engine):
    """
    Create a session factory with accounting-specific event listeners.
    
    Args:
        engine: The database engine to create sessions for.
        
    Returns:
        A sessionmaker that will create AccountingSession instances with proper event listeners.
    """
    factory = sessionmaker(
        bind=engine,
        class_=AccountingSession,
        info={
            "include_deleted": engine.get_execution_options().get("include_deleted", False),
            "ignore_isolation": engine.get_execution_options().get("ignore_isolation", False),
        }
    )
    
    # Register event listeners on this specific factory
    return register_accounting_events(factory)

def get_session(engine) -> Session:
    """
    Construct the accounting session.

    Args:
        engine: The database engine to create a session for.

    Returns:
        AccountingSession.
    """
    session_factory = get_session_factory(engine)
    return session_factory()
