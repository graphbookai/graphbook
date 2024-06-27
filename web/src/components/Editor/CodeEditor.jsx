import { useState, useCallback, useEffect } from 'react';
import CodeMirror from '@uiw/react-codemirror';
import { python } from '@codemirror/lang-python';
import { basicDark } from '@uiw/codemirror-theme-basic';
import { bbedit } from '@uiw/codemirror-theme-bbedit';
import { CloseOutlined, CheckOutlined, LoadingOutlined } from "@ant-design/icons";
import { theme } from 'antd';
import { useAPI } from '../../hooks/API';
import { md5 } from 'js-md5';
const { useToken } = theme;

import './code-editor.css';
const UPDATE_EVERY = 1 * 1000;
const defaultEditorState = {
    isLoading: true,
    prevHash: "",
    value: "",
    isSaved: true
};

// Create a function that generates an MD5 hash of the file content
const generateMD5 = (content) => {
    const hash = md5.create();
    hash.update(content);
    return hash.hex();
};

export function CodeEditor({closeEditor, name}) {
    const [codeEditorState, setCodeEditorState] = useState(defaultEditorState);
    const [currTimeout, setCurrTimeout] = useState(null);
    const API = useAPI();
    const token = useToken();

    let filepath = name;
    if (filepath[0] === '/') {
        filepath = filepath.slice(1);
    }

    useEffect(() => {
        const getFile = async () => {
            try {
                const file = await API.getFile(filepath);
                setCodeEditorState({ ...codeEditorState, isLoading: false, prevHash: generateMD5(file.content), value: file.content });
            } catch {
                setCodeEditorState({ ...codeEditorState, isLoading: true });
                console.log("Error getting file");
            }
        };
        if (API && filepath) {
            getFile();
        }
    }, [API]);

    const onChange = useCallback((val, viewUpdate) => {
        if (!API) {
            return;
        }

        setCodeEditorState({ ...codeEditorState, isSaved: false, value: val });
        if (currTimeout) {
            clearTimeout(currTimeout);
        }

        const timeout = setTimeout(async () => {
            console.log("Saving file...", filepath);
            try {
                await API.putFile(filepath, true, val, codeEditorState.prevHash);
                const newHash = generateMD5(val);
                setCodeEditorState({ ...codeEditorState, isSaved: true, prevHash: newHash, value: val });
            } catch {
                setCodeEditorState({ ...codeEditorState, isLoading: true });
                console.log("Error putting file");
            }
        }, UPDATE_EVERY);
        setCurrTimeout(timeout);
    }, [currTimeout, filepath, codeEditorState, API]);

    return (
        <div style={{height: '100%', display: 'flex', flexDirection: 'column'}}>
            <div style={{height: '24px', display: 'flex', flexDirection: 'row', justifyContent: 'space-between'}}>
                <div style={{display: 'flex', flexDirection: 'row'}}>
                    <div style={{margin: '5px', lineHeight: 1}}>{name}</div>
                    <div style={{margin: '5px', lineHeight: 1}}>
                        { codeEditorState.isSaved ?
                        <div><CheckOutlined style={{color:'green'}}/> Saved</div>
                        :
                        <div><LoadingOutlined/> Pending changes</div>
                        }
                    </div>
                </div>
                <CloseOutlined style={{float: 'right', margin: '5px'}} onClick={closeEditor}/>
            </div>
            <div style={{overflowY: 'scroll', resize: 'horizontal', paddingRight: '10px'}}>
                <CodeMirror
                    className='code-editor'
                    height='100%'
                    theme={token.theme.id == 0 ? bbedit : basicDark}
                    value={codeEditorState.value}
                    editable={!codeEditorState.isLoading}
                    extensions={[python()]}
                    onChange={onChange}
                />
            </div>

        </div>
    );
}
