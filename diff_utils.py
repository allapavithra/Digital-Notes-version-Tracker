import difflib
import html
from typing import List, Dict, Any, Tuple, Optional

def escape(t: str) -> str:
    return html.escape(t)

def generate_side_by_side_diff(text1: str, text2: str) -> Dict[str, Any]:
    """
    Returns data structured for side-by-side visualization, plus change counts.
    """
    # Normalize line endings
    text1 = text1.replace('\r\n', '\n') if text1 else ''
    text2 = text2.replace('\r\n', '\n') if text2 else ''

    lines1: List[str] = text1.split('\n')
    lines2: List[str] = text2.split('\n')
    
    sm = difflib.SequenceMatcher(None, lines1, lines2)
    
    diff_data: List[Tuple[Any, str, str, Any, str, str]] = [] 
    
    left_num: int = 1
    right_num: int = 1
    
    added_lines: int = 0
    deleted_lines: int = 0
    modified_lines: int = 0
    added_topics: set = set()
    
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == 'equal':
            for line in lines1[i1:i2]:
                diff_data.append((left_num, escape(line), 'diff-equal', right_num, escape(line), 'diff-equal'))
                left_num += 1
                right_num += 1
        elif tag == 'replace':
            max_len = max(i2 - i1, j2 - j1)
            for k in range(max_len):
                l_line_opt: Optional[str] = lines1[i1+k] if (i1+k) < i2 else None
                r_line_opt: Optional[str] = lines2[j1+k] if (j1+k) < j2 else None
                
                if l_line_opt is not None and r_line_opt is not None:
                    # Character level diff inside the line
                    l_line: str = l_line_opt
                    r_line: str = r_line_opt
                    sm_line = difflib.SequenceMatcher(None, l_line, r_line)
                    l_res: List[str] = []
                    r_res: List[str] = []
                    for wtag, wi1, wi2, wj1, wj2 in sm_line.get_opcodes():
                        if wtag == 'equal':
                            l_res.append(escape(l_line[wi1:wi2]))
                            r_res.append(escape(r_line[wj1:wj2]))
                        elif wtag == 'insert':
                            r_res.append('<span class="hl-add">' + escape(r_line[wj1:wj2]) + "</span>")
                            # Heuristic for topics
                            for word in r_line[wj1:wj2].split():
                                w: str = str(word)
                                if len(w) > 4 and w[0].isupper():
                                    added_topics.add(w.strip('.,?!()[]{}"\''))
                        elif wtag == 'delete':
                            l_res.append('<span class="hl-del">' + escape(l_line[wi1:wi2]) + "</span>")
                        elif wtag == 'replace':
                            l_res.append('<span class="hl-del">' + escape(l_line[wi1:wi2]) + "</span>")
                            r_res.append('<span class="hl-modify">' + escape(r_line[wj1:wj2]) + '</span>')
                            for word in r_line[wj1:wj2].split():
                                w: str = str(word)
                                if len(w) > 4 and w[0].isupper():
                                    added_topics.add(w.strip('.,?!()[]{}"\''))
                    
                    diff_data.append((left_num, "".join(l_res), 'diff-modify', right_num, "".join(r_res), 'diff-modify'))
                    left_num += 1
                    right_num += 1
                    modified_lines += 1
                elif l_line_opt is not None:
                    l_line: str = l_line_opt
                    diff_data.append((left_num, escape(l_line), 'diff-delete', '', '', 'diff-empty'))
                    left_num += 1
                    deleted_lines += 1
                elif r_line_opt is not None:
                    r_line: str = r_line_opt
                    diff_data.append(('', '', 'diff-empty', right_num, escape(r_line), 'diff-add'))
                    right_num += 1
                    added_lines += 1
                    for word in r_line.split():
                        w: str = str(word)
                        if len(w) > 4 and w[0].isupper():
                            added_topics.add(w.strip('.,?!()[]{}"\''))

        elif tag == 'delete':
            for line in lines1[i1:i2]:
                diff_data.append((left_num, escape(line), 'diff-delete', '', '', 'diff-empty'))
                left_num += 1
                deleted_lines += 1
        elif tag == 'insert':
            for line in lines2[j1:j2]:
                diff_data.append(('', '', 'diff-empty', right_num, escape(line), 'diff-add'))
                right_num += 1
                added_lines += 1
                for word in line.split():
                    w: str = str(word)
                    if len(w) > 4 and w[0].isupper():
                        added_topics.add(w.strip('.,?!()[]{}"\''))
                        
    summary: List[str] = []
    if added_lines > 0: summary.append(f"{added_lines} lines/points added")
    if deleted_lines > 0: summary.append(f"{deleted_lines} lines/points deleted")
    if modified_lines > 0: summary.append(f"{modified_lines} lines/points modified")
    if not summary: summary.append("No changes detected")
    
    final_topics: List[str] = list(added_topics)
    return {
        'diff': diff_data,
        'summary': summary,
        'added_topics': final_topics[:10]
    }

def generate_structured_diff(text1: str, text2: str) -> Dict[str, Any]:
    """
    Generates structured textual output of added, removed, and modified lines
    without relying on visual UI highlights.
    """
    text1 = text1.replace('\r\n', '\n') if text1 else ''
    text2 = text2.replace('\r\n', '\n') if text2 else ''

    lines1: List[str] = text1.split('\n')
    lines2: List[str] = text2.split('\n')
    
    sm = difflib.SequenceMatcher(None, lines1, lines2)
    
    added: List[Tuple[int, str]] = []
    removed: List[Tuple[int, str]] = []
    modified: List[Tuple[int, str, str]] = []
    
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == 'replace':
            max_len = max(i2 - i1, j2 - j1)
            for k in range(max_len):
                l_line_opt = lines1[i1+k] if (i1+k) < i2 else None
                r_line_opt = lines2[j1+k] if (j1+k) < j2 else None
                
                if l_line_opt is not None and r_line_opt is not None:
                    modified.append((j1+k+1, l_line_opt, r_line_opt))
                elif l_line_opt is not None:
                    removed.append((i1+k+1, l_line_opt))
                elif r_line_opt is not None:
                    added.append((j1+k+1, r_line_opt))
        elif tag == 'delete':
            for k, line in enumerate(lines1[i1:i2]):
                removed.append((i1+k+1, line))
        elif tag == 'insert':
            for k, line in enumerate(lines2[j1:j2]):
                added.append((j1+k+1, line))
                
    return {
        'added': added,
        'removed': removed,
        'modified': modified,
        'summary': {
            'added': len(added),
            'removed': len(removed),
            'modified': len(modified)
        }
    }
