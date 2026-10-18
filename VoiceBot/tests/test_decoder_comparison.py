import json
from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch
from services.decoder_comparison import compare_decoders


class DecoderComparisonTests(unittest.TestCase):
    def test_both_workers_receive_same_audio_and_requested_settings(self):
        paths=[]
        def worker(command,**kwargs):
            path=Path(command[command.index('--audio')+1]);paths.append(path)
            self.assertEqual(path.read_bytes(),b'one recording')
            self.assertEqual(command[command.index('--beam')+1],'6')
            method=command[command.index('--method')+1]
            return subprocess.CompletedProcess(command,0,json.dumps({'status':'ok','method':method,'text':'Hello'}),'')
        with patch('services.decoder_comparison.subprocess.run',side_effect=worker):
            result=compare_decoders(b'one recording',['greedy_search','modified_beam_search'],'models','cpu',2,6)
        self.assertEqual(paths[0],paths[1]);self.assertFalse(paths[0].exists())
        self.assertEqual([r['status'] for r in result],['ok','ok'])

    def test_native_unsupported_failure_does_not_lose_other_result(self):
        outcomes=[subprocess.CompletedProcess([],1,'','Unsupported decoding method: modified_beam_search'),
                  subprocess.CompletedProcess([],0,json.dumps({'status':'ok','method':'greedy_search','text':'Hello'}),'')]
        with patch('services.decoder_comparison.subprocess.run',side_effect=outcomes):
            result=compare_decoders(b'audio',['modified_beam_search','greedy_search'],'models','cpu',2)
        self.assertEqual(result[0]['status'],'unsupported');self.assertEqual(result[1]['text'],'Hello')

    def test_timeout_is_reported_and_next_method_runs(self):
        with patch('services.decoder_comparison.subprocess.run',side_effect=[subprocess.TimeoutExpired('worker',90),subprocess.CompletedProcess([],0,'{"status":"ok","method":"greedy_search"}','')]):
            result=compare_decoders(b'audio',['modified_beam_search','greedy_search'],'models','cpu',2)
        self.assertEqual(result[0]['status'],'error');self.assertEqual(result[1]['status'],'ok')

    def test_invalid_selections_never_launch_workers(self):
        with patch('services.decoder_comparison.subprocess.run') as worker:
            for methods in ([],['unknown'],['greedy_search','greedy_search']):
                with self.assertRaises(ValueError):compare_decoders(b'a',methods,'models','cpu',2)
            worker.assert_not_called()
