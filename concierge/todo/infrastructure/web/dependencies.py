from concierge.todo.infrastructure.configuration.container import build_task_controller
from concierge.todo.interfaces.controllers.task_controller import TaskController
from concierge.todo.interfaces.presenters.base import BaseTaskPresenter


def get_task_controller() -> TaskController:
    return build_task_controller()


def get_api_presenter() -> BaseTaskPresenter:
    return BaseTaskPresenter()
