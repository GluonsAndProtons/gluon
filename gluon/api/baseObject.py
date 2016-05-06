# All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

import datetime

import wsme
from wsme import types as wtypes
from pecan import rest
import wsmeext.pecan as wsme_pecan
from gluon.api import types
from gluon.core.manager import gluon_core_manager


class APIBase(wtypes.Base):

    # TBD
    created_at = wsme.wsattr(datetime.datetime, readonly=True)
    """The time in UTC at which the object is created"""

    # #TBD
    updated_at = wsme.wsattr(datetime.datetime, readonly=True)
    """The time in UTC at which the object is updated"""

    def as_dict(self):
        """Render this object as a dict of its fields."""
        return dict((k, getattr(self, k))
                    for k in self.fields
                    if hasattr(self, k) and
                    getattr(self, k) != wsme.Unset)

    def unset_fields_except(self, except_list=None):
        """Unset fields so they don't appear in the message body.

        :param except_list: A list of fields that won't be touched.

        """
        if except_list is None:
            except_list = []

        for k in self.as_dict():
            if k not in except_list:
                setattr(self, k, wsme.Unset)


class APIBaseObject(APIBase):

    _object_class = None

    @classmethod
    def class_builder(base_cls, name, object_class, attributes):
        new_cls = type(name, (base_cls,), attributes)
        new_cls._object_class = object_class
        return new_cls

    @classmethod
    def get_object_class(cls):
        return cls._object_class

    @classmethod
    def build(cls, db_obj):
        obj = cls()
        db_obj_dict = db_obj.as_dict()
        for field in cls._object_class.fields:
            # Skip fields we do not expose.
            if not hasattr(obj, field):
                continue
            setattr(obj, field, db_obj_dict.get(field, wtypes.Unset))
        return obj

    def to_db_object(self):
        new_DB_obj = self._object_class()
        for field in self._object_class.fields:
            if not hasattr(self, field) or not getattr(self, field):
                continue
            setattr(new_DB_obj, field, getattr(self, field))
        return new_DB_obj


class APIBaseList(APIBase):

    @classmethod
    def get_object_class(cls):
        return cls._API_object_class.get_object_class()

    @classmethod
    def class_builder(base_cls, name, list_name, API_object_class):
        new_cls = type(name, (base_cls,), {list_name: [API_object_class]})
        new_cls._list_name = list_name
        new_cls._API_object_class = API_object_class
        return new_cls

    @classmethod
    def build(cls, db_obj_list):
        obj = cls()
        setattr(obj, cls._list_name,
                [cls._API_object_class.build(db_obj)
                 for db_obj in db_obj_list])
        return obj


class RootObjectController(rest.RestController):
    ''' Root Objects are Objects of the API which
    do not have a parent
    '''

    @classmethod
    def class_builder(base_cls, name, API_object_class,
                      primary_key_type):
        new_cls = type(name, (base_cls,), {})
        new_cls._list_object_class = APIBaseList.class_builder(name + 'List',
                                                               name,
                                                               API_object_class)
        new_cls._API_object_class = API_object_class
        new_cls._primary_key_type = primary_key_type

        @wsme_pecan.wsexpose(new_cls._list_object_class, template='json')
        def get_all(self):
            return self._list_object_class.build(
                self._list_object_class.get_object_class().list())
        new_cls.get_all = classmethod(get_all)

        @wsme_pecan.wsexpose(new_cls._API_object_class, new_cls._primary_key_type,
                             template='json')
        def get_one(self, key):
            return self._API_object_class.build(
                self._API_object_class.get_object_class().get_by_primary_key(key))
        new_cls.get_one = classmethod(get_one)

        @wsme_pecan.wsexpose(new_cls._API_object_class,
                             body=new_cls._API_object_class, template='json',
                             status_code=201)
        def post(self, body):
            call_func = getattr(gluon_core_manager, 'create_%s' % self.__name__,
                                None)
            if not call_func:
                raise Exception('create_%s is not implemented' % self.__name__)
            return self._API_object_class.build(call_func(body.to_db_object()))
        new_cls.post = classmethod(post)

        return new_cls


class SubObjectController(RootObjectController):

    @classmethod
    def class_builder(base_cls, name, object_class, primary_key_type,
                      parent_identifier_type,
                      parent_attribute_name):
        new_cls = super(SubObjectController, base_cls).class_builder(
            name, object_class, primary_key_type)
        new_cls._parent_identifier_type = parent_identifier_type
        new_cls._parent_attribute_name = parent_attribute_name

        @wsme_pecan.wsexpose(new_cls._list_object_class, new_cls._parent_identifier_type,
                             template='json')
        def get_all(self, _parent_identifier):
            filters = {self._parent_attribute_name: _parent_identifier}
            return self._list_object_class.build(
                self._list_object_class.get_object_class().list(
                    filters=filters))
        new_cls.get_all = classmethod(get_all)

        @wsme_pecan.wsexpose(new_cls._API_object_class, 
                             new_cls._parent_identifier_type,
                             new_cls._primary_key_type,
                             template='json')
        def get_one(self, parent_identifier, key):
            filters = {self._parent_attribute_name: _parent_identifier}
            return self._API_object_class.build(
                self._API_object_class.get_object_class(
                ).get_by_primary_key(key, filters))
        new_cls.get_one = classmethod(get_one)

        @wsme_pecan.wsexpose(new_cls._API_object_class, new_cls._parent_identifier_type,
                             body=new_cls._API_object_class, template='json',
                             status_code=201)
        def post(self, parent_identifier, body):
            call_func = getattr(gluon_core_manager, 'create_%s' % self.__name__,
                                None)
            if not call_func:
                raise Exception('create_%s is not implemented' % self.__name__)
            return self._API_object_class.build(call_func(parent_identifier,
                                                          body.to_db_object()))
        new_cls.post = classmethod(post)

        return new_cls
