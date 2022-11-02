## HTTP Proxy
This is a simple proxy server that proxy network requests. The proxy support basic HTTP requests using HTTP/1.0 or HTTP/1.1 protocol.

---

#### Running the proxy
```sh
# format: python3 proxy.py <port> <image-flag> <attack-flag>
python3 proxy.py 8080 1 0
```
* `<port>` should be a valid open port
* flags should either be 1 or 0
  * Setting the `<image-flag>` will substitute all image req to https://www.comp.nus.edu.sg/~chanmc/change.jpg (see `ImageChangeTransformer` in `modules/extensions`)
  * Setting the `<attack-flag>` will transform all output response to a custom HTML resource. (see `AttackTransformer` in `modules/extensions`)

<br/>

To run the program in verbose mode, add the `-v` to the program argument
```sh
python3 proxy.py 8080 1 0 -v
```


### Testing the proxy
The easiest way to test the proxy is using the firefox browser. Follow the steps below to configure your browser for proxy server:
1. Open Settings
2. Search “Network Settings”
3. In Manual Proxy Configuration, enter the IP address and (listening) port number of your proxy server in HTTPS Proxy.
4. (Optional) If the setup does not work, try to check “Proxy DNS when using SOCKS v5”.
5. Visit any `http://` webpage and watch the requests in your proxy server.


### Customising your proxy

You can add more customised behaviour to your proxy by adding more extensions. Each extension can transform incoming and/or outgoing packets.

To add more extensions to the proxy server, simple create a new class inheriting `PacketTransformer` and add it into the proxy extensions.
