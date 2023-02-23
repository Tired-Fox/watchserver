# TODO

- [x] Add logic for serving custom error pages from sub directory
- [x] Test watch directories
- [x] Add better logic around custom callbacks
  - [x] Custom pattern match for updating keys
  - [x] Callbacks must have the signature `(root: str, src: str) -> list[str]`. The callbacks must take the servers root and the path of the source file that has been updated. Callbacks must return a list of strings. This can be empty, but the strings are patterns for what URLs to live reload/update.
- [x] Custom server path object that handles all need logic including isdir and isfile.
- [x] Live reload pushes and pulls from queue of updates
- [ ] Dynamic caching header add or remove
- [ ] Ability to remove a substring from the start of the path for the server routing
- [ ] Add ignore list
