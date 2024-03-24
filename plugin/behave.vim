if !has('python3')
    echomsg 'pybehavevim not loaded due to missing py3'
    finish
endif
if exists('g:loaded_pybehavevim')
    finish
endif
let g:loaded_pybehavevim = 1

python3 import pybehavevim.behave

command! FindBehave python3 pybehavevim.behave.findmain()
