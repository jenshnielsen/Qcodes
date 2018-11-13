import pika
import time
import numpy as np
import pytest
import pickle
from functools import partial


@pytest.fixture(scope='function')
def channel():
    connection = pika.BlockingConnection(pika.ConnectionParameters('localhost'))
    channel = connection.channel()
    channel.exchange_declare(exchange='mydata',
                             exchange_type='fanout')
    channel.queue_declare(queue='tordensky', durable=True)
    channel.queue_bind(exchange='mydata',
                       queue='tordensky')
    channel.queue_declare(queue='localstorage', durable=True)
    channel.queue_bind(exchange='mydata',
                       queue='localstorage')
    yield channel
    channel.close()
    connection.close()


def publish_data_in_mode(channel, data, mode):
    for i in range(1_000):
        channel.publish(exchange='mydata',
                        routing_key='',
                        body=data,
                        properties=pika.BasicProperties(delivery_mode=mode))


def gen_data(size):
    b = np.arange(size)
    c = np.arange(size)
    example_object = (('foo', b),
                      ('guf', c))
    data = pickle.dumps(example_object)
    return data


@pytest.mark.parametrize("size", [1, 100, 1000, 10000])
@pytest.mark.parametrize("mode", [1, 2])
@pytest.mark.parametrize("persistence", [False, True])
def test_send(benchmark, channel, size, mode, persistence):
    data = gen_data(size)
    if persistence:
        channel.confirm_delivery()
    functobench = partial(publish_data_in_mode, channel=channel,
                          data=data, mode=mode)
    benchmark(functobench)
