#!/usr/bin/env python3

import sys
sys.path.append('lib')

from ops.charm import CharmBase
from ops.framework import StoredState
from ops.main import main

from resources import OCIImageResource
from wrapper import FrameworkWrapper
from k8s import K8sPod, K8sPvc
from observers import (
    ConfigChangeObserver,
    RemovalObserver,
    StatusObserver,
    RelationObserver,
)
from mongodb_interface_provides import MongoDbServer
from builders import MongoBuilder, K8sBuilder
import logging

logger = logging.getLogger()


class MongoDbCharm(CharmBase):
    _state = StoredState()

    def __init__(self, *args):
        super().__init__(*args)
        self._framework_wrapper = FrameworkWrapper(self.framework, self._state)
        self._resources = {
            'mongodb-image': OCIImageResource('mongodb-image')
        }

        self._mongo_builder = MongoBuilder(
            self._framework_wrapper.app_name,
            self._framework_wrapper.config,
            self._resources,
            self._framework_wrapper.goal_state_units
        )

        if self._framework_wrapper.config['enable-sidecar']:
            self._resources['mongodb-sidecar-image'] = OCIImageResource(
                'mongodb-sidecar-image')

        self._pod = K8sPod(self._framework_wrapper.app_name)
        self._pvc = K8sPvc(self._framework_wrapper.app_name)
        self._mongodb = MongoDbServer(self, "mongo")

        self._k8s_builder = K8sBuilder(self._pvc)

        delegators = [
            (self.on.start, self.on_config_changed_delegator),
            (self.on.upgrade_charm, self.on_config_changed_delegator),
            (self.on.config_changed, self.on_config_changed_delegator),
            (self.on.update_status, self.on_update_status_delegator),
            (self._mongodb.on.new_client, self.on_new_client_delegator),
            (self.on.remove_pvc_action, self.on_remove_pvc_action_delegator),
        ]
        for delegator in delegators:
            self.framework.observe(delegator[0], delegator[1])

    def on_config_changed_delegator(self, event):
        logger.info('on_config_changed_delegator({})'.format(event))
        return ConfigChangeObserver(
            self._framework_wrapper,
            self._resources,
            self._pod,
            self._mongo_builder).handle(event)

    def on_remove_pvc_action_delegator(self, event):
        logger.info('on_remove_pvc_action_delegator({})'.format(event))
        return RemovalObserver(
            self._framework_wrapper,
            self._resources,
            self._pod,
            self._pvc,
            self._k8s_builder).handle(event)

    def on_new_client_delegator(self, event):
        logger.info('on_relation_changed_delegator({})'.format(event))
        return RelationObserver(
            self._framework_wrapper,
            self._resources,
            self._pod,
            self._mongo_builder).handle(event)

    def on_update_status_delegator(self, event):
        logger.info('on_update_status_delegator({})'.format(event))
        return StatusObserver(
            self._framework_wrapper,
            self._resources,
            self._pod,
            self._mongo_builder).handle(event)


if __name__ == "__main__":
    main(MongoDbCharm)
