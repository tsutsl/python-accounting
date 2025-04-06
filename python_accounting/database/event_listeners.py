# database/event_listeners.py
# Copyright (C) 2024 - 2028 the PythonAccounting authors and contributors
# <see AUTHORS file>
#
# This module is part of PythonAccounting and is released under
# the MIT License: https://www.opensource.org/licenses/mit-license.php

"""
This mixin provides logic for handling events in sqlalchemy's orm lifecycle
that are relevant to accounting.

"""
from datetime import datetime
from sqlalchemy import event, orm, and_, update
from sqlalchemy.orm.session import Session

from python_accounting.models import Entity, Recyclable, Transaction, Account, Ledger
from python_accounting.mixins import IsolatingMixin
from python_accounting.exceptions import MissingEntityError

def _filter_options(execute_state, option) -> bool:
    return (
        not execute_state.is_column_load
        and not execute_state.is_relationship_load
        and not execute_state.execution_options.get(option, False)
        and not execute_state.session.info.get(option, False)
    )

# Create standalone functions instead of class methods
def _add_filtering_criteria(execute_state) -> None:
    # Recycling filter
    if _filter_options(execute_state, "include_deleted"):
        execute_state.statement = execute_state.statement.options(
            orm.with_loader_criteria(
                Recyclable,
                lambda cls: and_(
                    cls.deleted_at == None,  # pylint: disable=singleton-comparison
                    cls.destroyed_at  # pylint: disable=singleton-comparison
                    == None,
                ),
                execute_state,
                include_aliases=True,
            )
        )

    # Entity filter
    if (
        _filter_options(execute_state, "ignore_isolation")
        and execute_state.statement.column_descriptions[0]["type"] is not Entity
    ):
        session_entity_id = execute_state.session.entity.id
        execute_state.statement = execute_state.statement.options(
            orm.with_loader_criteria(
                IsolatingMixin,
                lambda cls: cls.entity_id == session_entity_id,
                include_aliases=True,
            )
        )

def _set_session_entity(session, object_) -> None:
    if not hasattr(session, "entity") or session.entity is None:
        if isinstance(object_, Entity):
            session.entity = object_
        elif object_.entity_id is None:
            raise MissingEntityError
        else:
            session.entity = session.get(Entity, object_.entity_id)

    if (
        session.entity.reporting_period is None
        or session.entity.reporting_period.calendar_year != datetime.today().year
    ):
        session._set_reporting_period()

def _set_object_index(session, object_) -> None:
    if (isinstance(object_, (Account, Transaction))) and object_.id is None:
        object_.session_index = (
            len(
                [
                    t
                    for t in session.new
                    if isinstance(t, Transaction)
                    and t.transaction_type == object_.transaction_type
                ]
            )
            if isinstance(object_, Transaction)
            else len(
                [
                    a
                    for a in session.new
                    if isinstance(a, Account)
                    and a.account_type == object_.account_type
                ]
            )
        )

def _validate_model(session, _, __) -> None:
    for model in list(session.new) + list(session.dirty):
        if hasattr(model, "validate"):
            model.validate(session)

# The Ledger event handler stays at the model level but checks for accounting sessions
@event.listens_for(Ledger, "after_insert")
def _set_ledger_hash(mapper, connection, target):
    # Only proceed if session has our entity attribute (our custom session type)
    if hasattr(target, "_sa_instance_state") and \
       hasattr(target._sa_instance_state.session, "entity"):
        connection.execute(
            update(Ledger)
            .where(Ledger.id == target.id)
            .values(hash=target.get_hash(connection))
        )

def register_accounting_events(session_factory):
    """
    Register accounting-specific event listeners to a specific session factory
    rather than globally to the Session class.
    
    Args:
        session_factory: A sessionmaker instance
    
    Returns:
        The modified sessionmaker instance
    """
    event.listen(session_factory, "do_orm_execute", _add_filtering_criteria)
    event.listen(session_factory, "transient_to_pending", _set_session_entity)
    event.listen(session_factory, "transient_to_pending", _set_object_index)
    event.listen(session_factory, "before_flush", _validate_model)
    return session_factory

# Keep the class for backward compatibility, but it no longer registers global listeners
class EventListenersMixin:
    """
    Event Listeners class - now just a placeholder for backward compatibility.
    Global listeners are not registered anymore.
    """
    pass