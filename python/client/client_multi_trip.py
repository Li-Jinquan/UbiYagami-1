import os
import sys

from sqlalchemy import false

path = os.path.join(os.path.dirname(__file__), os.pardir)
sys.path.append(path)
# from client.client import Client
import h5py
import asyncio
import numpy as np
import asyncio
import struct
import multiprocessing
import time
from argparse import ArgumentParser
from data_type import OrderType, DirectionType, OperationType, Order, Quote, Trade
import logging
from connection.tcp_client import run_client

logger = logging.getLogger()
handler = logging.FileHandler('./ClientLogFile.log')
logging.basicConfig(level=logging.DEBUG)
formatter = logging.Formatter('%(asctime)s  %(name)s  %(levelname)s: %(message)s')
logger.addHandler(handler)
handler.setFormatter(formatter)
import datetime
import contextlib
from functools import partial
import psutil
import pysnooper
import gc


@contextlib.contextmanager
def record_time():
    try:
        start_time = datetime.datetime.now()
        logger.info('start: {}'.format(start_time))
        yield
    finally:
        logger.info('this code text need time: {}'.format(datetime.datetime.now() - start_time))


def read_binary_order_temp_file(data_file_path):
    struct_fmt = '=iiidii'  #
    struct_len = struct.calcsize(struct_fmt)
    struct_unpack = struct.Struct(struct_fmt).unpack_from
    results = []
    with open(data_file_path, "rb") as f:
        while True:
            data = f.read(struct_len)
            if not data: break
            s = struct_unpack(data)
            results.append(Order(s[0] + 1, s[1], s[2], s[3], s[4], s[5]))
    return results


class data_read:
    def __init__(self, data_file_path, client_id):
        self.trade_list = [[]] * 10
        # client_id used to identify different client server
        self.client_id = client_id
        self.all_page = []
        self.data_file_path = data_file_path

    # process all data, alter that then trans these data

    def data_read_mp(self, curr_stock_id):
        order_id_path = self.data_file_path + '/' + "order_id" + str(self.client_id) + ".h5"
        direction_path = self.data_file_path + '/' + "direction" + str(self.client_id) + ".h5"
        price_path = self.data_file_path + '/' + "price" + str(self.client_id) + ".h5"
        volume_path = self.data_file_path + '/' + "volume" + str(self.client_id) + ".h5"
        type_path = self.data_file_path + '/' + "type" + str(self.client_id) + ".h5"

        order_id_mtx = h5py.File(order_id_path, 'r')['order_id']
        direction_mtx = h5py.File(direction_path, 'r')['direction']
        price_mtx = h5py.File(price_path, 'r')['price']
        volume_mtx = h5py.File(volume_path, 'r')['volume']
        type_mtx = h5py.File(type_path, 'r')['type']
        # logger.info('读文件进程的内存使用：',psutil.Process(os.getpid()).memory_info().rss)
        # logger.info('读文件进程的内存使用：%.4f GB' % (psutil.Process(os.getpid()).memory_info().rss / 1024 / 1024 / 1024) )

        data_page_number = order_id_mtx.shape[0]
        data_row_number = order_id_mtx.shape[1]
        data_column_number = order_id_mtx.shape[2]
        per_stock_page_number = data_page_number // 10
        logger.info("page number is %d" % data_page_number)
        logger.info("data row number is%d" % data_row_number)
        logger.info("data column number is %d" % data_column_number)
        logger.info("per stock has %d page" % per_stock_page_number)
        # data transform
        # this implementation only works for small data(100x10x10 0.06 per stock 100x100x100 35s per stock, 100x1000x1000 1240s per stock, it's unaccecptable)
        logger.info("begin to process data")
        # print(curr_stock_id)
        logger.info("proceesing stock %d" % (curr_stock_id + 1))
        indexes = [i * 10 + curr_stock_id for i in range(0, per_stock_page_number)]
        curr_order_id_page = order_id_mtx[indexes,].reshape(-1).astype(np.int32)
        curr_direction_page = direction_mtx[indexes,].reshape(-1).astype(np.int32)
        curr_price_page = price_mtx[indexes,].reshape(-1)
        curr_volumn_page = volume_mtx[indexes,].reshape(-1).astype(np.int32)
        curr_type_page = type_mtx[indexes,].reshape(-1).astype(np.int32)
        curr_order_page = np.transpose(
            [curr_order_id_page, curr_direction_page, curr_price_page, curr_volumn_page, curr_type_page])
        del curr_order_id_page
        del curr_direction_page
        del curr_price_page
        del curr_volumn_page
        del curr_type_page
        gc.collect()
        # curr_order_id_page = order_id_mtx[curr_stock_id].reshape(-1)
        # curr_direction_page = direction_mtx[curr_stock_id].reshape(-1)
        # curr_price_page = price_mtx[curr_stock_id].reshape(-1)
        # curr_volumn_page = volume_mtx[curr_stock_id].reshape(-1)
        # curr_type_page = type_mtx[curr_stock_id].reshape(-1)
        # for i in range(1, per_stock_page_number):
        # temp_order_id_page = order_id_mtx[i * 10 + curr_stock_id].reshape(-1)
        # curr_order_id_page = np.concatenate((curr_order_id_page, temp_order_id_page))
        # del temp_order_id_page
        # temp_direction_page = direction_mtx[i * 10 + curr_stock_id].reshape(-1)
        # curr_direction_page = np.concatenate((curr_direction_page, temp_direction_page))
        # del temp_direction_page
        # temp_price_page = price_mtx[i * 10 + curr_stock_id].reshape(-1)
        # curr_price_page = np.concatenate((curr_price_page, temp_price_page))
        # del temp_price_page
        # temp_volume_page = volume_mtx[i * 10 + curr_stock_id].reshape(-1)
        # curr_volumn_page = np.concatenate((curr_volumn_page, temp_volume_page))
        # del temp_volume_page
        # temp_type_page = type_mtx[i * 10 + curr_stock_id].reshape(-1)
        # curr_type_page = np.concatenate((curr_type_page, temp_type_page))
        # del temp_type_page
        # curr_order_page = np.transpose([curr_order_id_page, curr_direction_page, curr_price_page, curr_volumn_page, curr_type_page])
        # sort curr_order_page by order_id
        logger.info('排序前的内存使用：%.4f GB' % (psutil.Process(os.getpid()).memory_info().rss / 1024 / 1024 / 1024))
        curr_order_page = curr_order_page[curr_order_page[:, 0].argsort()]
        self.all_page.append(curr_order_page)
        logger.info('排序后的内存使用：%.4f GB' % (psutil.Process(os.getpid()).memory_info().rss / 1024 / 1024 / 1024))

        # temp_file_path = self.data_file_path + '/team-3/' + 'temp' + str(curr_stock_id + 1)

        logger.info(str(os.getpid()) + 'to list前的内存使用：%.4f GB' % (
                    psutil.Process(os.getpid()).memory_info().rss / 1024 / 1024 / 1024))
        # res = curr_order_page.tolist()
        logger.info('to_list后的内存使用：%.4f GB' % (psutil.Process(os.getpid()).memory_info().rss / 1024 / 1024 / 1024))

        return (curr_stock_id, curr_order_page)


def print_error(value):
    logger.info("Error reason: ", value)


def write_data2file(args):
    curr_stock_id = args[0]
    curr_order_page = args[1]
    temp_file_path = '/data/team-3/' + 'temp' + str(curr_stock_id + 1)
    # temp_file_path = 'F:/temp'+ str(curr_stock_id + 1)
    with open(temp_file_path, 'wb+') as f:
        f.write(b''.join(
            map(lambda x: struct.pack("=iiidii", int(curr_stock_id), int(x[0]), int(x[1]), x[2], int(x[3]), int(x[4])),
                curr_order_page)))
        f.close()
    logger.info(
        str(os.getpid()) + '写入的内存使用：%.4f GB' % (psutil.Process(os.getpid()).memory_info().rss / 1024 / 1024 / 1024))
    del curr_order_page


def make_batches(size, batch_size):
    nb_batch = int(np.ceil(size / float(batch_size)))
    return [(i * batch_size, min(size, (i + 1) * batch_size)) for i in range(0, nb_batch)]


@pysnooper.snoop(output="trans_loop.log")
def wait_hook_watch(order_id, stock_id, hook_mtx, trade_lists):
    while order_id > hook_mtx[stock_id][0][0]:
        hook_mtx[stock_id] = hook_mtx[stock_id][1:]

    if order_id == hook_mtx[stock_id][0][0]:
        target_stk_code = hook_mtx[stock_id][0][1]
        target_trade_idx = hook_mtx[stock_id][0][2]
        if len(trade_lists[target_stk_code - 1]) < target_trade_idx - 1:
            # logger.debug("corresponding stock %d 's tradelist is not enough when stock %d order_id %d inquire hook")
            return True
    return False


def wait_hook(order_id, stock_id, hook_mtx, trade_lists):
    while order_id > hook_mtx[stock_id][0][0]:
        hook_mtx[stock_id] = hook_mtx[stock_id][1:]

    if order_id == hook_mtx[stock_id][0][0]:
        target_stk_code = hook_mtx[stock_id][0][1]
        target_trade_idx = hook_mtx[stock_id][0][2]
        if len(trade_lists[target_stk_code - 1]) < target_trade_idx - 1:
            logger.debug("Order {order.order_id} of stock {stock_id} waiting for target trade ")
            return True
    return False


def get_final_order(order: Order, stock_id, hook_mtx, trade_lists):
    if order.order_id == hook_mtx[stock_id][0][0]:
        target_stk_code = hook_mtx[stock_id][0][1]
        target_trade_idx = hook_mtx[stock_id][0][2]
        arg = hook_mtx[stock_id][0][3]

        if trade_lists[target_stk_code - 1][target_trade_idx - 1] > arg:
            logger.debug(f"Hook not valid, send empty order {order.order_id} of stock {stock_id}")
            order.volume = 0

        hook_mtx[stock_id] = hook_mtx[stock_id][1:]
    return order


def put_data_in_queue(send_queue, data_file_path, client_id, trade_lists):
    logger.info("COMMUNICATE PROCESS: CLIENT_ID %d " % (client_id))
    # append squares of mylist to queue
    '''
    for i in range(10):
        temp_file_path = data_file_path + '/' + 'temp' + str(i + 1)
        order_list = read_binary_order_temp_file(temp_file_path)
        for i in range(len(order_list)):
    '''
    hook_mtx = h5py.File(data_file_path + '/' + "hook.h5", 'r')['hook']
    order_list = []
    # asyncio.run(put_in_queue(data_file_path, send_queue, hook_mtx, hook_position, trade_lists))
    stock_id = 0
    hook_current_positon = hook_mtx[:, 0, 0]
    hook_current_index = [0] * 10
    curr_order_position = [0] * 10
    while not np.all(np.array(curr_order_position) == -1):
        stock_id %= 10
        batch_size = 100
        temp_file_path = '/data/team-3/' + 'temp' + str(stock_id + 1)
        order_list = read_binary_order_temp_file(temp_file_path)
        last_order_position = curr_order_position[stock_id]
        while curr_order_position[stock_id] != -1 and last_order_position+batch_size > curr_order_position[stock_id]:
            temp_order = order_list[curr_order_position[stock_id]]
            order_id = temp_order.order_id
            if order_id < hook_current_positon[stock_id]:
                send_queue.put(temp_order)
                curr_order_position[stock_id] += 1
            else:
                # curr_order_position[stock_id] == hook_current_positon:
                # 判断要不要继续,只管这一个订单
                if hook_current_index[stock_id] >= hook_mtx[stock_id].shape[0]:
                    send_queue.put(temp_order)
                    curr_order_position[stock_id] += 1
                else:
                    hook_order = hook_mtx[stock_id, hook_current_index[stock_id]]
                    target_stk_code = hook_order[1]
                    target_trade_idx = hook_order[2]
                    arg = hook_order[3]
                    if len(trade_lists[target_stk_code - 1]) < target_trade_idx:
                        #不够，要等
                        break
                    else:
                        if trade_lists[target_stk_code - 1][target_trade_idx - 1] > arg:
                            #set order.volume=0
                            temp_order.volume = 0
                        send_queue.put(temp_order)
                        hook_current_positon[stock_id] = hook_mtx[stock_id, hook_current_index[stock_id], 0]
                        hook_current_index[stock_id] += 1
                        curr_order_position[stock_id] += 1
            if curr_order_position[stock_id] >= len(order_list):
                curr_order_position[stock_id] = -1
                break
        stock_id += 1



def communicate_with_server(send_queue, receive_queue, client_id, data_file_path, trade_lists):
    """
    function to square a given list
    """
    run_client(receive_queue, send_queue)


def write_result_to_file(receive_queue, res_file_path, client_id, trade_lists):
    """
    function to print queue elements
    """
    logger.info("WRITE FILE PROCESS: RES PATH %s CLIENT_ID %d " % (res_file_path, client_id))
    while True:
        if not receive_queue.empty():
            Trade_Item = receive_queue.get_nowait()
            if Trade_Item == "DONE":
                break
            else:
                stock_id = Trade_Item.stk_code
                volume = Trade_Item.volume
                row = trade_lists[stock_id - 1]  # take the  row
                row.append(volume)  # change it
                trade_lists[stock_id - 1] = row
                # logger.info('GET TRADE {}'.format(type(b''.join(Trade_Item.to_bytes()))))
                # logger.info('GET TRADE {}'.format(b''.join(Trade_Item.to_bytes())))
                # trade_lists[stock_id - 1].append(volume)
                res_path = res_file_path + '/' + 'trade' + str(stock_id)
                with open(res_path, 'ab') as f:
                    f.write(Trade_Item.to_bytes())
        else:
            time.sleep(0.05)
    '''     
    for stock_id in range(10):
        res_path = res_file_path + '/' + 'trade' + str(stock_id + 1)
        with open(res_path, 'wb') as f:
            f.write(b''.join(map(lambda x: x.to_bytes(), trade_lists[stock_id])))
    '''


if __name__ == "__main__":
    # input list
    parser = ArgumentParser()
    parser.add_argument("-f", "--filepath", help="data file folder path")
    parser.add_argument("-r", "--respath", help="result folder path")
    parser.add_argument("-c", "--client_id", help="client_id, which is 1 or 2")
    args = parser.parse_args()
    logger.info("===============begin to read data==============")
    with record_time():
        order_data = data_read(args.filepath, args.client_id)
        batch_size = 4
        query_list = make_batches(10, batch_size)
        # order_data.data_read()
        # order_id_mtx,direction_mtx, price_mtx, volume_mtx, type_mtx, per_stock_page_number = order_data.data_read()
        # final_func = partial(mpread,order_id_mtx=order_id_mtx,direction_mtx=direction_mtx, price_mtx=price_mtx, volume_mtx=volume_mtx, type_mtx=type_mtx, per_stock_page_number=per_stock_page_number)
        # order_data.data_read_mp(0)
        for start, end in query_list:
            pool = multiprocessing.Pool(batch_size)
            for curr_stock_id in range(start, end):
                pool.apply_async(order_data.data_read_mp, args=(curr_stock_id,), callback=write_data2file,
                                 error_callback=print_error)
            pool.close()
            pool.join()

    manager = multiprocessing.Manager()
    # a simple implemment to achieve result
    order_id_position = [0] * 10
    trade_lists = manager.list()
    for i in range(10):
        trade_lists.append([])

    logger.info("===============data read finished==============")
    logger.info("==========================client server %s begin===========================" % args.client_id)

    # creating multiprocessing Queue
    send_queue = multiprocessing.Queue()
    receive_queue = multiprocessing.Queue()
    # read_data_from_file(args.filepath, int(args.client_id),)
    # creating new processes
    process_list = []
    # process_read_data_from_file = multiprocessing.Process(target=read_data_from_file, args=(args.filepath, int(args.client_id), ))
    process_put_data_in_queue = multiprocessing.Process(target=put_data_in_queue, args=(
    send_queue, args.filepath, int(args.client_id), trade_lists))
    process_communicate_with_server = multiprocessing.Process(target=communicate_with_server, args=(
    send_queue, receive_queue, int(args.client_id), args.filepath, trade_lists))
    process_write_result_to_file = multiprocessing.Process(target=write_result_to_file, args=(
    receive_queue, args.respath, int(args.client_id), trade_lists))

    # process_read_data_from_file.start()
    # process_read_data_from_file.join()
    process_put_data_in_queue.start()
    # process_put_data_in_queue.join()
    process_communicate_with_server.start()
    # process_communicate_with_server.join()
    process_write_result_to_file.start()
    # process_write_result_to_file.join()
    # process_list.append(process_read_data_from_file)
    process_list.append(process_put_data_in_queue)
    process_list.append(process_communicate_with_server)
    process_list.append(process_write_result_to_file)
    for p in process_list:
        p.join()