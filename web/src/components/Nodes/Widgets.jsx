import { Typography, theme } from 'antd';
import { useCallback, useState } from 'react';
import CodeMirror from '@uiw/react-codemirror';
import { python } from '@codemirror/lang-python';
import { basicDark } from '@uiw/codemirror-theme-basic';
import { bbedit } from '@uiw/codemirror-theme-bbedit';
import { Graph } from '../../graph';
import { useReactFlow } from 'reactflow';
const { Text } = Typography;
const { useToken } = theme;

export function Widget({ id, type, name, value }) {
    const { setNodes } = useReactFlow();

    const onChange = useCallback((value) => {
        setNodes(nodes => {
            return Graph.editParamData(id, name, {value}, nodes);
        });
    }, []);

    switch (type) {
        case 'number':
            return <NumberWidget name={name} def={value} onChange={onChange}/>
        case 'string':
            return <StringWidget name={name} def={value} onChange={onChange}/>
        case 'function':
            return <FunctionWidget name={name} def={value} onChange={onChange}/>
        default:
            return <StringWidget name={name} def={value} onChange={onChange}/>
    }
}

export function NumberWidget({ name, def, onChange }) {
    return (
        <InputNumber onChange={onChange} label={name} defaultValue={def}/>
    );
}

export function StringWidget({ name, def, onChange }) {
    return (
        <Input onChange={onChange} label={name} defaultValue={def}/>
    );
}

export function FunctionWidget({ name, def, onChange }) {
    const token = useToken();

    return (
        <CodeMirror
            value={def}
            theme={token.theme.id == 0 ? bbedit : basicDark}
            height='100%'
            width='100%'
            minWidth='300px'
            extensions={[python()]}
            onChange={onChange}
        />
    );
}

function InputNumber({ onChange, label, defaultValue }) {
    const { token } = useToken();
    const defaultFocusedStyle = { border: `1px solid ${token.colorBorder}` };
    const [ focusedStyle, setFocusedStyle ] = useState(defaultFocusedStyle)
    const containerStyle = {
    };
    const inputStyle = {
        backgroundColor: token.colorBgContainer,
        color: token.colorText,
    };
    const labelStyle = {
        backgroundColor: token.colorBgContainer
    }
    const handleChange = (e) => {
        onChange(Number(e.target.value));
    };
    const onInputFocus = useCallback((isFocused) => {
        if (isFocused) {
            setFocusedStyle({ border: `1px solid ${token.colorInfoActive}` });
        } else {
            setFocusedStyle(defaultFocusedStyle);
        }
    });

    return (
        <div style={{containerStyle, ...focusedStyle}} className="input-container">
            <Text style={labelStyle}>{label}</Text>
            <input
                onFocus={()=>onInputFocus(true)}
                onBlur={()=>onInputFocus(false)}
                onChange={handleChange}
                style={inputStyle}
                className="input"
                type="number"
                defaultValue={defaultValue}
            />
        </div>
    );
}


function Input({ onChange, label, defaultValue }) {
    const { token } = useToken();
    const defaultFocusedStyle = { border: `1px solid ${token.colorBorder}` };
    const [ focusedStyle, setFocusedStyle ] = useState(defaultFocusedStyle)
    const containerStyle = {
    };
    const inputStyle = {
        backgroundColor: token.colorBgContainer,
        color: token.colorText,
    };
    const labelStyle = {
        backgroundColor: token.colorBgContainer
    }
    const handleChange = (e) => {
        onChange(e.target.value);
    };

    const onInputFocus = useCallback((isFocused) => {
        if (isFocused) {
            setFocusedStyle({ border: `1px solid ${token.colorInfoActive}` });
        } else {
            setFocusedStyle(defaultFocusedStyle);
        }
    });

    return (
        <div style={{containerStyle, ...focusedStyle}} className="input-container">
            <Text style={labelStyle}>{label}</Text>
            <input
                onFocus={()=>onInputFocus(true)}
                onBlur={()=>onInputFocus(false)}
                onChange={handleChange}
                style={inputStyle}
                className="input"
                type="text"
                defaultValue={defaultValue}
            />
        </div>
    );
}
