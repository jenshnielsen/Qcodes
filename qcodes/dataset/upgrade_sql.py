from .sqlite_base import atomicTransaction, get_user_version, set_user_version

def upgrade_db_0_to_1(connection):

    userversion = get_user_version(connection)
    if userversion != 0:
        raise RuntimeError("trying to upgrade from version 0"
                           " but your database is version"
                           " {}".format(userversion))
    sql = 'ALTER TABLE "runs" ADD COLUMN "quality"'

    atomicTransaction(connection, sql)
    set_user_version(connection, 1)

