# TODO

- [x] Add logic for serving custom error pages from sub directory
- [x] Test watch directories
- [x] Add better logic around custom callbacks
  - [x] Custom pattern match for updating keys
  - [x] Callbacks must have the signature `(root: str, src: str) -> list[str]`. The callbacks must take the servers root and the path of the source file that has been updated. Callbacks must return a list of strings. This can be empty, but the strings are patterns for what URLs to live reload/update.
  - [x] Callback class to inherit from to allow for customization along side of default impls
- [x] Custom server path object that handles all needed logic including isdir and isfile.
- [x] Live reload pushes and pulls from queue of updates
- [x] Add ignore list
- [ ] Ability to remove a substring from the start of the path for the server routing
- [ ] Dynamic caching header add or remove
