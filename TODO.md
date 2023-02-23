# TODO

- [x] Add logic for serving custom error pages from sub directory
- [x] Test watch directories
- [ ] Add better logic around custom callbacks
  - [x] Custom pattern match for updating keys
  - [x] Callbacks must have the signature `(root: str, src: str) -> tuple[bool, str|None, str|None]`. The callbacks must take the servers root and the path of the source file that has been updated. Callbacks must return the state to set the key(s) to, the exact key to update and pattern of additional keys to update.
- [x] Custom server path object that handles all need logic including isdir and isfile.
- [ ] Dynamic caching header add or remove
