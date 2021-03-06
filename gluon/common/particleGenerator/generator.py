import os
import pkg_resources
import yaml

DataBaseModelGeneratorInstance = None
APIGeneratorInstance = None
model = None
sql_model_build = False
queued_build_api = False
package_name = "unknown"

def set_package(package):
    global package_name
    package_name = package

# Singleton generator
def load_model():
        global model
        if not model:
            model = {}
            for f in pkg_resources.resource_listdir(package_name, 'models'):
                f = "models/" + f
                with pkg_resources.resource_stream(package_name, f) as fd:
                    model.update(yaml.safe_load(fd))


def build_sql_models(base):
    from gluon.common.particleGenerator.DataBaseModelGenerator import DataBaseModelProcessor
    load_model()
    global DataBaseModelGeneratorInstance
    if not DataBaseModelGeneratorInstance:
        DataBaseModelGeneratorInstance = DataBaseModelProcessor()
        DataBaseModelGeneratorInstance.add_model(model)
        DataBaseModelGeneratorInstance.build_sqla_models(base)


def build_api(root):
    from gluon.common.particleGenerator.ApiGenerator import APIGenerator
    global DataBaseModelGeneratorInstance
    global APIGeneratorInstance
    load_model()
    if not APIGeneratorInstance:
        APIGeneratorInstance = APIGenerator(DataBaseModelGeneratorInstance.db_models)
        APIGeneratorInstance.add_model(model)
        APIGeneratorInstance.create_api(root)

def getDataBaseGeneratorInstance():
    global DataBaseModelGeneratorInstance
    return DataBaseModelGeneratorInstance