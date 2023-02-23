# Livereload

A easy to use fully features live reloading and file watching http server. The server uses watchdog, queue, and ThreadedServer to create a live reloading environment. The interactions are fully customizable where a callback is called for file creation, update, and removal. The defaults are intuitive, but user customization is also easy.

Features:
- Live reload
  - on html change
  - on static, `css` or `js`, change
- Auto load custom error pages
- Ignore patterns for files and directories
- User defined values with smart defaults
  - Watch paths: defaults to `cwd`
  - Ignore files/paths: defaults to nothing being ignored
  - File event callbacks: defaults to reloading page on html change or static file change
  - server port: defaults to `3031`
  - server host: defaults to `localhost`
  - base directory, this is where the server discovers custom error files: defaults to `cwd`
  - root directory, this is where the server attaches and serves from: defaults to `cwd`
  - suppress, stops all server logging, defaults to `False`
- Auto open server in browser