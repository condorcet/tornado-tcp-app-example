from tornado import gen
from tornado.ioloop import IOLoop
from tornado.iostream import StreamClosedError
from tornado.options import define, options

from app.app_client import ApplicationSourceClient, ApplicationListenerClient, ClientException
from app.app_server import ApplicationServer
from base.source import Source
from base.exceptions import SourceException, InvalidMessageException

# source controller
@gen.coroutine
def start_source():
    if not options.sid:
        print('source id `sid` must be defined')
        return
    source = Source(options.sid, options.status)
    print('source\t"{}"\t"{}"({})'.format(source.source_id, source.status_str, source.status))
    client = ApplicationSourceClient(source)
    print('connect to server...')
    try:
        yield client.connect(options.host, options.port[0])
        print('success!')

        # simple command interpreter
        @gen.coroutine
        def exec_command(command):
            if not command:
                return
            if command == 'status':
                print('Accepted statuses:', *Source.STATUS.keys())
                value = input('status (must be integer):')
                try:
                    value = int(value)
                    client.source.status = value
                except ValueError:
                    print('value of status must be integer')
                except SourceException:
                    print('status "{}" not accepted'.format(value))
            elif command == 'send':
                data = {}
                if input('input message data?(y/n)') == 'y':
                    print('---data input mode---')
                    while True:
                        key = input('key:')
                        value = input('value (must be integer):')
                        try:
                            data[key] = int(value)
                        except ValueError:
                            print('value must be integer')
                        cont = input('continue? (n)')
                        if cont == 'n':
                            break
                if len(data) > 0:
                    print('Message data:')
                    print(*data.items(), sep='\n')
                if input('Send message?(y/n)') == 'y':
                    try:
                        yield client.send_message(data)
                        # wait for response
                        response = yield client.listen()
                        print(response)
                    except ClientException as e:
                        print('Error:', e)
                        print('message not sent')
                    except InvalidMessageException:
                        print('response message broken')
                else:
                    print('sending cancelled')
                    return
        # client loop
        try:
            print('-' * 8)
            print('available commands:')
            print('- status', 'changed status of source')
            print('- send', 'send message to server')
            while True:
                command = input('cmd:')
                yield exec_command(command)
        except KeyboardInterrupt:
            client.stop()
            IOLoop.current().stop()

    except StreamClosedError:
        print('connection closed by server')
        client.stop()
        IOLoop.current().stop()


# server controller
def start_server():
    if options.port:
        try:
            ApplicationServer.SOURCE_PORT = options.port[0]
            ApplicationServer.LISTENER_PORT = options.port[1]
        except (IndexError, TypeError):
            pass
    # start server
    server = ApplicationServer()
    server.listen(port=ApplicationServer.SOURCE_PORT, address=options.host)
    server.listen(port=ApplicationServer.LISTENER_PORT, address=options.host)
    try:
        IOLoop.current().start()
    except KeyboardInterrupt:
        print('server stopped')

# listener controller
@gen.coroutine
def start_listener():
    client = ApplicationListenerClient()
    try:
        yield client.connect(options.host, options.port[0])
        while True:
            message = yield client.listen()
            print(message.decode(), end='')
    except StreamClosedError:
        print('connection closed by server')


#  main controller
def main():
    try:
        if options.type == 'server':
            start_server()
        elif options.type == 'source':
            IOLoop.current().run_sync(start_source)
        elif options.type == 'listener':
            IOLoop.current().run_sync(start_listener)
    except KeyboardInterrupt:
        print('closed')


#  command line params
define('type', 'source', help='start app server/source/listener')
define('host', 'localhost', help='server host')
define('port', [8888], type=int, multiple=True, help='''To start server use pair <source_port>,<listener_port>.
                                            To start source/listener enter single value.
                                            Default 8888,8889''')
define('sid', None, help='source id')
define('status', None, help='initial status of source')

if __name__ == '__main__':
    options.parse_command_line()
    main()
