import org.apache.lucene.codecs.*;
import org.apache.lucene.index.*;
import org.apache.lucene.store.*;
import java.nio.file.*;
import java.io.*;
import java.util.*;

/** Reads stored fields of one Lucene segment (Shamela 4 store) without opening the whole index.
 *  usage: DumpSeg <dir> <segName> <out.jsonl> [idPrefix ...]  (idPrefix filters on field "id", e.g. "6170-") */
public class DumpSeg {
  static String esc(String s){StringBuilder b=new StringBuilder();for(char c:s.toCharArray()){switch(c){case '"':b.append("\\\"");break;case '\\':b.append("\\\\");break;case '\n':b.append("\\n");break;case '\r':b.append("\\r");break;case '\t':b.append("\\t");break;default: if(c<0x20)b.append(String.format("\\u%04x",(int)c)); else b.append(c);}}return b.toString();}
  public static void main(String[] a) throws Exception {
    Path p=Paths.get(a[0]); String seg=a[1];
    byte[] si=Files.readAllBytes(p.resolve(seg+".si"));
    int off=4; int n=si[off]; off+=1+n+4; byte[] id=Arrays.copyOfRange(si,off,off+16);
    Directory dir=new NIOFSDirectory(p);
    Codec codec=Codec.forName("Lucene104");
    SegmentInfo info=codec.segmentInfoFormat().read(dir,seg,id,IOContext.DEFAULT);
    Directory cfs= info.getUseCompoundFile()? codec.compoundFormat().getCompoundReader(dir,info): dir;
    FieldInfos fis=codec.fieldInfosFormat().read(cfs,info,"",IOContext.DEFAULT);
    StoredFieldsReader r=codec.storedFieldsFormat().fieldsReader(cfs,info,fis,IOContext.DEFAULT);
    List<String> pre=new ArrayList<>(); for(int i=3;i<a.length;i++)pre.add(a[i]);
    int max=info.maxDoc(), out=0;
    try(Writer w=new BufferedWriter(new OutputStreamWriter(new FileOutputStream(a[2]),"UTF-8"))){
      for(int d=0; d<max; d++){
        final Map<String,String> m=new LinkedHashMap<>();
        r.document(d,new StoredFieldVisitor(){
          public Status needsField(FieldInfo fi){return Status.YES;}
          public void stringField(FieldInfo fi,String v){m.merge(fi.name,v,(x,y)->x+"\u0001"+y);}
          public void intField(FieldInfo fi,int v){m.put(fi.name,""+v);}
          public void longField(FieldInfo fi,long v){m.put(fi.name,""+v);}
        });
        if(!pre.isEmpty()){String k=m.getOrDefault("id","");boolean ok=false;for(String q:pre)if(k.startsWith(q))ok=true;if(!ok)continue;}
        StringBuilder b=new StringBuilder("{");boolean f=true;
        for(var e:m.entrySet()){if(!f)b.append(',');f=false;b.append('"').append(esc(e.getKey())).append("\":\"").append(esc(e.getValue())).append('"');}
        w.write(b.append("}\n").toString()); out++;
      }
    }
    System.err.println(seg+" maxDoc="+max+" written="+out+" fields="+fis.size());
  }
}
