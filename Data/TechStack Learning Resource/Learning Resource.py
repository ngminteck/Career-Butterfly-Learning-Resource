import spacy
import pandas as pd
import pypandoc
import csv
import os
from os import listdir
from os.path import isfile, join
import shutil
import zipfile
import html2text


class Skill:
    def __init__(self, name, keyword, groups=None):
        filename = name
        filename = filename.replace('/', '-')
        filename = filename.replace("\\", '-')
        filename = filename + ".html"
        path = os.path.join("skill", filename)
        path = path.replace("\\", '/')
        self.resource_path = path  # for the resource path
        self.keyword_search = keyword  # keyword for searching LLM
        self.group_set = set()
        if groups is not None:
            self.UpdateGroupSet(groups)

    def UpdateGroupSet(self, groups):
        self.group_set.update(groups)
        # print("skill group set updated.")

    def ChangeKeyword(self, keyword):
        self.keyword_search = keyword


class Group:
    def __init__(self, name, skills):
        filename = name
        filename = filename.replace('/', '-')
        filename = filename.replace("\\", '-')
        filename = filename + ".html"
        path = os.path.join("group", filename)
        path = path.replace("\\", '/')
        self.resource_path = path  # for the resource path
        self.keyword_search = name + " in tech"  # keyword for searching LLM
        self.skill_set = skills

    def UpdateSkillSet(self, skill):
        self.skill_set.update(skill)
        # print("group skill set updated.")

    def ChangeKeyword(self, keyword):
        self.keyword_search = keyword


class TechStack:
    def __init__(self):
        self.nlp = spacy.load('en_core_web_md')
        self.skill_dict_list = {}
        self.group_dict_list = {}
        self.exact_match_replace_dict_list = {}
        self.partial_match_replace_dict_list = {}
        self.vector_group_dict_list = {}
        self.ignore_set = set()
        self.not_found_dict_list = {}
        self.three_word_skill_classification_set = set()
        self.two_word_skill_classification_set = set()
        self.one_word_skill_classification_set = set()
        self.backup_keyword_dict_list = {}
        self.leetcode_list = ["c++", "c", "c#", "python", "java", "javascript", "typescript", "php", "swift", "kotlin",
                              "go", "ruby", "scala", "rust", "racket"]
        self.leetcode_company_dict_list = {}
        self.leetcode_overall_frequency_dict_list = {}
        self.ImportIgnoreSet()
        self.AllThisWillBeRemoveOnceFinalize()
        self.ImportClassificationSet()
        self.ImportSkillDictList()
        self.GroupTextVectorization()
        self.InitLeetCodeCompanyNameDictList()
        self.InitLeetcodeOverallFrequencyDictList()

    def GenerateLearningResource(self, your_skills, job_skills, company_name, generated_directory):
        result_dict = {"Leetcode Question": None, "Skill Learning Resource Content": None,
                       "Skill Learning Resource Remarks": str("")}
        if not os.path.exists("learning resource/" + generated_directory):
            os.makedirs("learning resource/" + generated_directory)

        for key in job_skills:
            text = key
            text = text.lower()
            if text in self.leetcode_list:
                result_dict["Leetcode Question"] = self.GenerateLeetcodeResource(company_name, generated_directory)
                break
        difference_skill_dict_list = {}
        # difference_skill_dict_list = [dict_ for dict_ in job_skills if not any(dict_ == dict2 for dict2 in your_skills)]
        difference_skill_dict_list = job_skills
        if len(difference_skill_dict_list) != 0:
            skill_result_dict = self.GenerateSkillResource(difference_skill_dict_list, generated_directory)
            result_dict["Skill Learning Resource Content"] = skill_result_dict["Skill Learning Resource Content"]
            result_dict["Skill Learning Resource Remarks"] = skill_result_dict["Skill Learning Resource Remarks"]

        if result_dict["Leetcode Question"] is not None or result_dict["Skill Learning Resource Content"] is not None:
            self.ZipLearningResource(generated_directory)
        return result_dict

    @staticmethod
    def ZipLearningResource(generated_directory):
        directory_path = "learning resource/" + generated_directory
        zip_filename = "learning resource/" + generated_directory + "/learning resource.zip"

        with zipfile.ZipFile(zip_filename, 'w') as zipf:
            for folder_name, sub_folders, filenames in os.walk(directory_path):
                for filename in filenames:
                    file_path = os.path.join(folder_name, filename)
                    zipf.write(file_path, arcname=filename)

    def GenerateLeetcodeResource(self, company, generated_directory):
        leetcode_dict_list = {}
        check_company = company
        check_company = check_company.lower()
        company_name_to_search = str("")
        for c in self.leetcode_company_dict_list:
            check = c.lower()
            if check == check_company:
                company_name_to_search = c
                break
        if company_name_to_search == "":
            shutil.copyfile("leetcode/leetcode learning resource.html",
                            "learning resource/" + generated_directory + "/leetcode learning resource.html")
            shutil.copyfile("leetcode/leetcode learning resource.docx",
                            "learning resource/" + generated_directory + "/leetcode learning resource.docx")
            df = pd.read_csv("leetcode/Top 100 Question List.csv")
            questions_content = str("")
            for index, row in df.iterrows():
                no = str(row['No'])
                title = str(row['Title'])
                link = str(row['Link'])
                path = "leetcode/Question/" + no + ".html"
                if os.path.isfile(path):
                    with open(path, "r", encoding="utf-8") as file:
                        file_content = file.read()

                        questions_content += "<h1><u><b>"
                        questions_content += no
                        questions_content += ". "
                        questions_content += title
                        questions_content += "</b></u></h1>\n"
                        questions_content += link
                        questions_content += "\n"
                        questions_content += file_content

                        h = html2text.HTML2Text()
                        h.ignore_links = False
                        h.inline_links = False
                        h.reference_links = False
                        string_format = h.handle(file_content)
                        string_format = string_format.replace("**", "")
                        leetcode_dict_list[no] = no + ". " + title + "\n" + link + "\n\n" + string_format
                        file.close()

            with open("learning resource/" + generated_directory + "/leetcode question.html", 'w',
                      encoding='utf-8') as file:
                file.write(questions_content)
                file.close()
            pypandoc.convert_text(questions_content, 'docx', format='html',
                                  outputfile='learning resource/' + generated_directory + '/leetcode question.docx')
            df[company + " Company Frequency"] = 0
            df["Overall Frequency"] = df["Frequency"]
            df = df.drop(columns=['Frequency'])
            df.to_csv("learning resource/" + generated_directory + "/leetcode question list.csv", encoding='utf-8',
                      index=False)
            return leetcode_dict_list
        else:
            html_content = ""
            title = "<h1><u><b>" + company + " Leetcode Tag Type Appear in the Question Count</b></u></h1>\n"
            html_content += title
            html_content += "<table>\n"
            html_content += "<tr>\n"
            html_content += "  <th>Tag</th>\n"
            html_content += "  <th>Count</th>\n"
            html_content += "</tr>\n"
            df = pd.read_csv("leetcode/Top Tag/" + company_name_to_search + ".csv")
            for index, row in df.iterrows():
                html_content += "<tr>\n"
                tag_html = "  <td>" + str(row["Tag"]) + "</td>\n"
                count_html = "  <td>" + str(row["Appearance"]) + "</td>\n"
                html_content += tag_html
                html_content += count_html
                html_content += "</tr>\n"
            html_content += "</table>\n"
            with open("leetcode/leetcode learning resource.html", "r", encoding="utf-8") as file:
                html_content += file.read()
                file.close()
            with open("learning resource/" + generated_directory + "/leetcode learning resource.html", 'w',
                      encoding='utf-8') as file:
                file.write(html_content)
                file.close()
            pypandoc.convert_text(html_content, 'docx', format='html', outputfile="learning resource/" + generated_directory + "/leetcode learning resource.docx")
            df1 = pd.read_csv("leetcode/Companies Leetcode/" + company_name_to_search + ".csv")
            df1[company + " Company Frequency"] = df1["Frequency"]
            df1 = df1.drop(columns=['Frequency'])
            df1["Overall Frequency"] = str("")
            for index, row in df1.iterrows():
                no = str(row['No'])
                if no in self.leetcode_overall_frequency_dict_list:
                    df1.at[index, "Overall Frequency"] = self.leetcode_overall_frequency_dict_list[no]
            df = pd.read_csv("leetcode/Top 100 Question List.csv")
            df[company + " Company Frequency"] = 0
            df["Overall Frequency"] = df['Frequency']
            df = df.drop(columns=['Frequency'])
            appended_df = pd.concat([df1, df], ignore_index=True)
            appended_df = appended_df.drop_duplicates(keep='first')
            final_df = appended_df.head(100).copy()
            final_df.to_csv("learning resource/" + generated_directory + "/leetcode question list.csv",
                            encoding='utf-8', index=False)
            questions_content = ""
            for index, row in final_df.iterrows():
                no = str(row['No'])
                title = str(row['Title'])
                link = str(row['Link'])
                path = "leetcode/Question/" + no + ".html"
                if os.path.isfile(path):
                    with open(path, "r", encoding="utf-8") as file:
                        file_content = file.read()

                        questions_content += "<h1><u><b>"
                        questions_content += no
                        questions_content += ". "
                        questions_content += title
                        questions_content += "</b></u></h1>\n"
                        questions_content += link
                        questions_content += "\n"
                        questions_content += file_content

                        h = html2text.HTML2Text()
                        h.ignore_links = False
                        h.inline_links = False
                        h.reference_links = False
                        string_format = h.handle(file_content)
                        string_format = string_format.replace("**", "")
                        leetcode_dict_list[no] = no + ". " + title + "\n" + link + "\n\n" + string_format
                        file.close()

            with open("learning resource/" + generated_directory + "/leetcode question.html", 'w', encoding='utf-8') as file:
                file.write(questions_content)
                file.close()
            pypandoc.convert_text(questions_content, 'docx', format='html', outputfile="learning resource/" + generated_directory + "/leetcode question.docx")
            return leetcode_dict_list

    def GenerateSkillResource(self, skills, generated_directory):
        result_dict = {"Skill Learning Resource Content": None, "Skill Learning Resource Remarks": str("")}

        result_dict["Skill Learning Resource Remarks"], document_prepare_set = self.GenerateSkillResourcePreProcessing(
            skills, result_dict["Skill Learning Resource Remarks"])
        if len(document_prepare_set) == 0:
            return result_dict

        result_dict["Skill Learning Resource Remarks"], result_dict["Skill Learning Resource Content"] = self.GenerateSkillResourceContent(skills, document_prepare_set, result_dict["Skill Learning Resource Remarks"], generated_directory)
        return result_dict

    def GenerateSkillResourcePreProcessing(self, skills, remarks):
        document_prepare_set = set()

        for key, value in skills.items():
            remarks, skills[key] = self.SkillLearningResourceFilter(key, value, remarks)
            if skills[key] != "":
                remarks, document_prepare_set = self.SkillLearningResourceSearch(key, skills[key], document_prepare_set, remarks)
        return remarks, document_prepare_set

    def GenerateSkillResourceContent(self, skills, document_prepare_set, remarks, generated_directory):
        skill_dict = {}
        html_content = ""
        for d in document_prepare_set:
            if d in self.skill_dict_list:
                v = self.skill_dict_list.get(d)
                path = v.resource_path
            elif d in self.skill_dict_list:
                v = self.group_dict_list.get(d)
                path = v.resource_path
            else:
                continue
            if not os.path.isfile(path):
                if len(remarks) != 0:
                    remarks += "\n"
                remarks += "can't generate content for "
                remarks += d.title()
            else:
                with open(path, "r", encoding="utf-8") as file:
                    title = d.title()
                    html_content += "<h1><u><b>"
                    html_content += title
                    html_content += "</b></u></h1>"
                    file_content = file.read()
                    html_content += file_content
                    h = html2text.HTML2Text()
                    h.ignore_links = False
                    h.inline_links = False
                    h.reference_links = True
                    skill_dict[title] = h.handle(file_content)
                file.close()
        with open("learning resource/" + generated_directory + "/skill learning resource.html", 'w',
                  encoding='utf-8') as file:
            file.write(html_content)
            file.close()
        pypandoc.convert_text(html_content, 'docx', format='html',
                              outputfile="learning resource/" + generated_directory + "/skill learning resource.docx")
        return remarks, skill_dict

    def SkillLearningResourceFilter(self, key, text, remarks):
        text = text.lower()
        text = text.replace("/", " ")
        if text.find('(') != -1:
            text = text.split("(")[0]
            text = text.rsplit()[0]
        if text in self.ignore_set:
            if len(remarks) != 0:
                remarks += "\n"
            remarks += key
            remarks += " not found"
            return remarks, str("")
        if text in self.exact_match_replace_dict_list:
            text = self.exact_match_replace_dict_list.get(text)
        words = text.split()
        new_text = ""
        for word in words:
            if word in self.partial_match_replace_dict_list:
                new_text += self.partial_match_replace_dict_list.get(word)
                new_text += " "
            else:
                new_text += word
                new_text += " "
        new_text = new_text[:-1]
        lower_key = key.lower()
        if lower_key != new_text:
            if len(remarks) != 0:
                remarks += "\n"
            remarks += key
            remarks += " also known as "
            remarks += new_text.title()
        return remarks, new_text

    def SkillLearningResourceSearch(self, key, text, document_prepare_set, remarks):
        if text in self.skill_dict_list:
            document_prepare_set.add(text)
            return remarks, document_prepare_set

        if text in self.group_dict_list:
            document_prepare_set.add(text)
            return remarks, document_prepare_set

        # check for . - space and .js
        for sdl in self.skill_dict_list:

            check1 = sdl
            if check1.endswith('s'):
                check1 = check1[:-1]
            check2 = text
            if check2.endswith('s'):
                check2 = check2[:-1]
            if check1 == check2:
                document_prepare_set.add(sdl)
                return remarks, document_prepare_set
            check1 = sdl
            check1 = check1.replace(".", "")
            check2 = text
            check2 = check2.replace(".", "")
            if check1 == check2:
                document_prepare_set.add(sdl)
                return remarks, document_prepare_set
            check1 = sdl
            check1 = check1.replace("-", " ")
            check2 = text
            check2 = check2.replace("-", " ")
            if check1 == check2:
                document_prepare_set.add(sdl)
                return remarks, document_prepare_set
            check1 = sdl
            check1 = check1.replace(" ", "")
            check2 = text
            check2 = check2.replace(" ", "")
            if check1 == check2:
                document_prepare_set.add(sdl)
                return remarks, document_prepare_set
            check1 = sdl
            check1 = check1.replace(".js", "")
            check1 = check1.replace("js", "")
            check2 = text
            check2 = check2.replace(".js", "")
            check2 = check2.replace("js", "")
            if check1 == check2:
                document_prepare_set.add(sdl)
                return remarks, document_prepare_set

        found = False
        words = text.split()
        # check word by word
        for word in words:
            if word in self.skill_dict_list:
                document_prepare_set.add(word)
                if len(remarks) != 0:
                    remarks += "\n"
                remarks += key
                remarks += " also known as "
                remarks += word.title()
                found = True
            elif word in self.group_dict_list:
                document_prepare_set.add(word)
                if len(remarks) != 0:
                    remarks += "\n"
                remarks += key
                remarks += " also known as "
                remarks += word.title()
                found = True

        if not found:
            if len(remarks) != 0:
                remarks += "\n"
            remarks += key
            remarks += " not found"
        return remarks, document_prepare_set

    def AddSkillDictList(self, name, keyword, groups=None):
        if name not in self.skill_dict_list:
            self.skill_dict_list[name] = Skill(name, keyword, groups)
            # print(name,"added in skill_dict_list.")
            if groups is not None:
                for g in groups:
                    if g in self.group_dict_list:
                        self.group_dict_list.get(g).UpdateSkillSet({name})
                        # print(name,"added in",g,".")
                    else:
                        self.group_dict_list[g] = Group(g, {name})
                        # print("new group:",g,"have been created and added",name,".")
        else:
            self.UpdateSkillDictList(name, groups)

    def ReClassificationSkillDictList(self, name, keyword, groups):
        search_keyword = keyword
        if name in self.backup_keyword_dict_list:
            search_keyword = self.backup_keyword_dict_list[name]
        self.AddSkillDictList(name, search_keyword, groups)

    def UpdateSkillDictList(self, name, groups):
        if name in self.skill_dict_list:
            self.skill_dict_list[name].UpdateGroupSet(groups)

    def AddGroupDictList(self, name, skills):
        if skills is not None:
            if name in self.group_dict_list:
                self.UpdateGroupDictList(name, skills)
            else:
                found_set = set()
                for s in skills:
                    if s in self.skill_dict_list:
                        self.skill_dict_list[s].UpdateGroupSet({name})
                        found_set.add(s)
                        # print(s,"added in",name,"group set.")
                self.group_dict_list[name] = Group(name, found_set)

    def UpdateGroupDictList(self, name, skills):
        if name in self.group_dict_list:
            found_set = set()
            for s in skills:
                if s in self.skill_dict_list:
                    found_set.add(s)
            self.group_dict_list[name].UpdateSkillSet(found_set)
        else:
            self.AddGroupDictList(name, skills)

    def AddNotFoundDictList(self, name, keyword):
        if name not in self.not_found_dict_list:
            path = "unclassified"
            self.not_found_dict_list[name] = Skill(name, path, keyword)

    def ImportIgnoreSet(self):
        f = open("ignore.txt", "r")
        for c in f:
            c = c.replace("\n", "")
            self.ignore_set.add(c)
        f.close()

    def ImportClassificationSet(self):
        file = open("three word skill classification.txt", "r")
        for word in file:
            word = word.replace("\n", "")
            self.three_word_skill_classification_set.add(word)
        file.close()
        file = open("two word skill classification.txt", "r")
        for word in file:
            word = word.replace("\n", "")
            self.two_word_skill_classification_set.add(word)
        file.close()
        file = open("one word skill classification.txt", "r")
        for word in file:
            word = word.replace("\n", "")
            self.one_word_skill_classification_set.add(word)
        file.close()

    def ExportSkillDictList(self):
        file_path = "skills.csv"
        with open(file_path, 'w', newline='') as file:
            writer = csv.writer(file)
            writer.writerow(["Name", "Search Keyword", "Resource Path", "Groups"])
            for key, value in self.skill_dict_list.items():
                name = key
                search = value.keyword_search
                path = value.resource_path
                groups = ""

                for g in value.group_set:
                    groups += "["
                    groups += g
                    groups += "]"

                writer.writerow([name, search, path, groups])
            file.close()
        with open('skills.txt', 'w') as f:
            for i in self.skill_dict_list:
                f.write(i)
                f.write("\n")
            f.close()

    def ImportSkillDictList(self):
        df = pd.read_csv("skills.csv")
        for index, row in df.iterrows():
            name = str(row['Name'])
            keyword = str(row['Search Keyword'])
            groups = str(row['Groups'])
            groups_set = None
            groups = groups.replace('[', '')
            groups_list = groups.split(']')
            if len(groups_list) > 0:
                groups_list = groups_list[:-1]
                groups_set = set()
                for g in groups_list:
                    groups_set.add(g)
            # auto create group also
            self.AddSkillDictList(name, keyword, groups_set)

    def ExportGroupDictList(self):
        file_path = "groups.csv"
        with open(file_path, 'w', newline='') as file:
            writer = csv.writer(file)
            writer.writerow(["Name", "Search Keyword", "Resource Path", "skills"])
            for key, value in self.group_dict_list.items():
                name = key
                search = value.keyword_search
                path = value.resource_path
                skills = ""
                for s in value.skill_set:
                    skills += "["
                    skills += s
                    skills += "]"
                writer.writerow([name, search, path, skills])
            file.close()

    def ExportMatchReplaceDictList(self):
        file_path = "exact match.csv"
        with open(file_path, 'w', newline='') as file:
            writer = csv.writer(file)
            writer.writerow(["Word", "Replace"])
            for key, value in self.exact_match_replace_dict_list.items():
                writer.writerow([key, value])
            file.close()
        file_path = "partial match.csv"
        with open(file_path, 'w', newline='') as file:
            writer = csv.writer(file)
            writer.writerow(["Word", "Replace"])
            for key, value in self.partial_match_replace_dict_list.items():
                writer.writerow([key, value])
            file.close()

    def ExportNotFoundSet(self):
        file_path = "not found.csv"
        with open(file_path, 'w', newline='') as file:
            writer = csv.writer(file)
            writer.writerow(["Name", "Search Keyword", "Resource Path"])
            for key, value in self.not_found_dict_list.items():
                name = key
                search = value.keyword_search
                path = "skill unclassified/not tech/" + name + ".html"

                writer.writerow([name, search, path])
            file.close()

    def GroupTextVectorization(self):
        for word in self.group_dict_list:
            if self.nlp.vocab[word].has_vector:
                vector_word = self.nlp(word)
                if vector_word not in self.vector_group_dict_list:
                    self.vector_group_dict_list[vector_word] = set()
                self.vector_group_dict_list[vector_word].add(word)

    def VectorSearch(self, word):
        if self.nlp.vocab[word].has_vector:
            vector_word = self.nlp(word)
            for vw in self.vector_group_dict_list:
                similarity_score = vector_word.similarity(vw)
                if similarity_score >= 0.9:
                    for w in self.vector_group_dict_list[vw]:
                        print(w)

    def CopyReplaceFolder(self, source_dir, dest_dir, filename):
        if dest_dir == "unknown":
            keyword = filename + " in tech"
        else:
            keyword = filename
        self.ReClassificationSkillDictList(filename, keyword, {dest_dir})
        dest_dir = "skill classified/" + dest_dir
        if not os.path.exists(dest_dir):
            os.makedirs(dest_dir)
        source_path_doc = source_dir + "/" + filename + ".docx"
        source_path_html = source_dir + "/" + filename + ".html"
        destination_path_doc = dest_dir + "/" + filename + ".docx"
        destination_path_html = dest_dir + "/" + filename + ".html"
        if source_path_doc != destination_path_doc:
            shutil.copyfile(source_path_doc, destination_path_doc)
        if source_path_html != destination_path_html:
            shutil.copyfile(source_path_html, destination_path_html)

    @staticmethod
    def MakeDocsFromHtml():
        directory = 'skill unclassified/not tech/'
        filenames = [f for f in listdir(directory) if isfile(join(directory, f))]
        for f in filenames:
            print(f)
            words = f.rsplit(".")
            extension = words[len(words) - 1]
            if extension == "html":
                filename = f.replace(".html", "")
                pypandoc.convert_file(directory + "/" + f, 'docx', outputfile=directory + "/" + filename + ".docx")

    def DeleteAllSkillFile(self):
        for directory in self.three_word_skill_classification_set:
            path = "skill classified/" + directory
            if os.path.isdir(path):
                for filename in os.listdir(path):
                    file_path = os.path.join(path, filename)
                    try:
                        if os.path.isfile(file_path) or os.path.islink(file_path):
                            os.unlink(file_path)
                        elif os.path.isdir(file_path):
                            shutil.rmtree(file_path)
                    except Exception as e:
                        print(f'Failed to delete {file_path}. Reason: {e}')
        for directory in self.two_word_skill_classification_set:
            path = "skill classified/" + directory
            if os.path.isdir(directory):
                for filename in os.listdir(path):
                    file_path = os.path.join(path, filename)
                    try:
                        if os.path.isfile(file_path) or os.path.islink(file_path):
                            os.unlink(file_path)
                        elif os.path.isdir(file_path):
                            shutil.rmtree(file_path)
                    except Exception as e:
                        print(f'Failed to delete {file_path}. Reason: {e}')
        for directory in self.one_word_skill_classification_set:
            path = "skill classified/" + directory
            if os.path.isdir(path):
                for filename in os.listdir(path):
                    file_path = os.path.join(path, filename)
                    try:
                        if os.path.isfile(file_path) or os.path.islink(file_path):
                            os.unlink(file_path)
                        elif os.path.isdir(file_path):
                            shutil.rmtree(file_path)
                    except Exception as e:
                        print(f'Failed to delete {file_path}. Reason: {e}')
        source_dir = 'skill'
        destination_dir = 'skill classified/unknown'
        os.makedirs(destination_dir, exist_ok=True)

        for file_name in os.listdir(source_dir):
            source_file = os.path.join(source_dir, file_name)
            destination_file = os.path.join(destination_dir, file_name)
            shutil.copy(source_file, destination_file)

    @staticmethod
    def FilterHtmlContent(text_content):
        text_content = text_content.lower()
        text_content = text_content.replace("[1]", "")
        text_content = text_content.replace("[2]", "")
        text_content = text_content.replace("[3]", "")
        text_content = text_content.replace("[4]", "")
        text_content = text_content.replace("[5]", "")
        text_content = text_content.replace("[6]", "")
        text_content = text_content.replace("[7]", "")
        text_content = text_content.replace("[8]", "")
        text_content = text_content.replace("[9]", "")
        text_content = text_content.replace("[0]", "")
        text_content = text_content.replace("[", "")
        text_content = text_content.replace("]", "")
        text_content = text_content.replace("(", "")
        text_content = text_content.replace(")", "")
        text_content = text_content.replace("*", "")
        text_content = text_content.replace("\"", "")
        text_content = text_content.replace("’s", "")
        text_content = text_content.replace("!", "")
        text_content = text_content.replace(":", "")
        text_content = text_content.replace(",", "")
        text_content = text_content.replace("\n", " ")
        text_content = text_content.replace("/", " ")
        text_content = text_content.replace("-", " ")
        return text_content

    def SkillReClassification(self):
        self.backup_keyword_dict_list.clear()
        for s in self.skill_dict_list:
            self.backup_keyword_dict_list[s] = self.skill_dict_list[s].keyword_search

        self.skill_dict_list.clear()
        self.group_dict_list.clear()
        self.vector_group_dict_list.clear()
        self.DeleteAllSkillFile()
        h = html2text.HTML2Text()
        h.ignore_links = False
        h.inline_links = False
        h.reference_links = True
        directory = 'skill classified/unknown'
        filenames = [f for f in listdir(directory) if isfile(join(directory, f))]

        for f in filenames:
            words = f.rsplit(".")
            extension = words[len(words) - 1]
            if extension == "html":
                filename = f.replace(".html", "")
                with open(directory + "/" + f, 'r', encoding="utf-8") as file:
                    html_content = file.read()
                    file.close()
                text_content = self.FilterHtmlContent(h.handle(html_content))
                words = text_content.split()
                have_classified = False
                for i in range(len(words)):
                    first_word = words[i]
                    if first_word.endswith('.'):
                        first_word = first_word[:-1]

                    one_word = first_word
                    one_word = one_word.replace("microservices", "microservice")
                    one_word = one_word.replace("protocols", "protocol")
                    one_word = one_word.replace("networks", "network")
                    one_word = one_word.replace("website", "web")
                    one_word = one_word.replace("test", "testing")
                    one_word = one_word.replace("visualizations", "visualization")
                    one_word = one_word.replace("aws", "amazon")

                    if one_word in self.one_word_skill_classification_set:
                        self.CopyReplaceFolder(directory, one_word, filename)
                        have_classified = True

                    if one_word == "ai":
                        one_word = "artificial intelligence"
                        if one_word in self.two_word_skill_classification_set:
                            self.CopyReplaceFolder(directory, one_word, filename)
                            have_classified = True
                    if one_word == "api":
                        one_word = "application programming interface"
                        if one_word in self.three_word_skill_classification_set:
                            self.CopyReplaceFolder(directory, one_word, filename)
                            have_classified = True
                    if one_word == "nlp":
                        one_word = "natural language processing"
                        if one_word in self.three_word_skill_classification_set:
                            self.CopyReplaceFolder(directory, one_word, filename)
                            have_classified = True

                    if i + 1 >= len(words):
                        break
                    second_word = words[i + 1]
                    if second_word.endswith('.'):
                        second_word = second_word[:-1]

                    two_word = first_word + " " + second_word
                    two_word = two_word.replace(" servers", " server")
                    two_word = two_word.replace(" services", " service")
                    two_word = two_word.replace(" applications", " application")
                    two_word = two_word.replace(" apps", " application")
                    two_word = two_word.replace(" app", " application")
                    two_word = two_word.replace(" databases", " database")
                    two_word = two_word.replace(" machines", " machine")
                    two_word = two_word.replace("website", "web")

                    if two_word in self.two_word_skill_classification_set:
                        self.CopyReplaceFolder(directory, two_word, filename)
                        have_classified = True

                    if i + 2 >= len(words):
                        break
                    third_word = words[i + 2]
                    if third_word.endswith('.'):
                        third_word = third_word[:-1]
                    three_word = first_word + " " + second_word + " " + third_word
                    if three_word in self.three_word_skill_classification_set:
                        self.CopyReplaceFolder(directory, three_word, filename)
                        have_classified = True

                if have_classified:
                    file_path = directory + "/" + filename + ".html"
                    if os.path.isfile(file_path):
                        os.remove(file_path)
                    else:
                        print(f"The file {file_path} does not exist.")
                    file_path = directory + "/" + filename + ".docx"
                    if os.path.isfile(file_path):
                        os.remove(file_path)
                    else:
                        print(f"The file {file_path} does not exist.")
                else:
                    self.ReClassificationSkillDictList(filename, filename + " in tech", {"unknown"})

        self.GroupTextVectorization()
        self.ExportSkillDictList()
        self.ExportGroupDictList()

    def ClassificationUnClassifiedSkill(self):
        h = html2text.HTML2Text()
        h.ignore_links = False
        h.inline_links = False
        h.reference_links = True
        directory = 'skill unclassified/not tech'
        filenames = [f for f in listdir(directory) if isfile(join(directory, f))]
        ignore_word_list = ["a", "an", "the", "of", "on", "as", "by", "to", "with", "for", "is", "are", "was", "were",
                            "in"]
        tech_word_list = ["software", "application", "applications", "platform", "platforms", "api", "web", "website",
                          "network", "networks", "security", "architecture", "development", "system", "systems",
                          "language", "cloud", "data", "open", "source", "windows"]
        for f in filenames:
            words = f.rsplit(".")
            extension = words[len(words) - 1]
            if extension == "html":
                with open(directory + "/" + f, 'r', encoding="utf-8") as file:
                    html_content = file.read()
                    file.close()
                text_content = self.FilterHtmlContent(h.handle(html_content))
                words = text_content.split()
                is_tech = False
                for i in range(len(words)):
                    if words[i] in tech_word_list:
                        is_tech = True
                        break
                if is_tech:
                    source_file = os.path.join("skill unclassified/not tech", f)
                    destination_file = os.path.join("skill unclassified/tech", f)
                    shutil.copy(source_file, destination_file)

    def FindClassificationKeyword(self):
        h = html2text.HTML2Text()
        h.ignore_links = False
        h.inline_links = False
        h.reference_links = True
        directory = 'skill classified/unknown'
        filenames = [f for f in listdir(directory) if isfile(join(directory, f))]
        one_word_dict_list = {}
        two_word_dict_list = {}
        three_word_dict_list = {}
        ignore_word_list = ["a", "an", "the", "of", "on", "as", "by", "to", "with", "for", "is", "are", "was", "were",
                            "in"]
        for f in filenames:
            words = f.rsplit(".")
            extension = words[len(words) - 1]
            if extension == "html":
                with open(directory + "/" + f, 'r', encoding="utf-8") as file:
                    html_content = file.read()
                    file.close()
                text_content = self.FilterHtmlContent(h.handle(html_content))
                words = text_content.split()
                for i in range(len(words)):
                    first_word = words[i]
                    if '1.' in first_word:
                        break
                    if first_word.endswith('.'):
                        first_word = first_word[:-1]
                    if first_word in ignore_word_list:
                        continue
                    one_word = first_word
                    if one_word not in one_word_dict_list:
                        one_word_dict_list[one_word] = 0
                    one_word_dict_list[one_word] += 1

                    second_word = words[i + 1]
                    if second_word.endswith('.'):
                        second_word = second_word[:-1]
                    if second_word in ignore_word_list:
                        continue
                    two_word = first_word + " " + second_word
                    if two_word not in two_word_dict_list:
                        two_word_dict_list[two_word] = 0
                    two_word_dict_list[two_word] += 1

                    third_word = words[i + 2]
                    if third_word.endswith('.'):
                        third_word = third_word[:-1]
                    if third_word in ignore_word_list:
                        continue
                    three_word = first_word + " " + second_word + " " + third_word
                    if three_word not in three_word_dict_list:
                        three_word_dict_list[three_word] = 0
                    three_word_dict_list[three_word] += 1
        with open('count one word.txt', 'w', encoding="utf-8") as f:
            for s in sorted(one_word_dict_list, key=one_word_dict_list.get, reverse=True):
                f.write(str(s) + " - " + str(one_word_dict_list[s]))
                f.write('\n')
            file.close()
        with open('count two word.txt', 'w', encoding="utf-8") as f:
            for s in sorted(two_word_dict_list, key=two_word_dict_list.get, reverse=True):
                f.write(str(s) + " - " + str(two_word_dict_list[s]))
                f.write('\n')
            file.close()
        with open('count three word.txt', 'w', encoding="utf-8") as f:
            for s in sorted(three_word_dict_list, key=three_word_dict_list.get, reverse=True):
                f.write(str(s) + " - " + str(three_word_dict_list[s]))
                f.write('\n')
            file.close()

    def InitLeetCodeCompanyNameDictList(self):
        f = open("leetcode/companies.txt", "r")

        for c in f:
            c = c.replace("\n", "")
            key = c
            key = key.lower()
            self.leetcode_company_dict_list[key] = c
        f.close()

    def InitLeetcodeOverallFrequencyDictList(self):
        df = pd.read_csv("leetcode/Question List.csv")
        for index, row in df.iterrows():
            self.leetcode_overall_frequency_dict_list[str(row["No"])] = str(row["Frequency"])

    def AllThisWillBeRemoveOnceFinalize(self):

        self.exact_match_replace_dict_list["aws"] = "amazon web services"
        self.exact_match_replace_dict_list["tdd"] = "testing"
        self.exact_match_replace_dict_list["webdriver"] = "web crawler"
        self.exact_match_replace_dict_list["vbnet"] = "visual basic .net"
        self.exact_match_replace_dict_list["vb.net"] = "visual basic .net"
        self.exact_match_replace_dict_list["vb"] = "visual basic"
        self.exact_match_replace_dict_list["html5"] = "html"
        self.exact_match_replace_dict_list["svn"] = "subversion"
        self.exact_match_replace_dict_list["rdbms"] = "relational"
        self.exact_match_replace_dict_list["unity3d"] = "unity"
        self.exact_match_replace_dict_list["mssql"] = "microsoft sql"
        self.exact_match_replace_dict_list["shaders"] = "shader"
        self.exact_match_replace_dict_list["uat"] = "testing"
        self.exact_match_replace_dict_list["mui"] = "material ui"
        self.exact_match_replace_dict_list["gui"] = "graphical user interface"
        self.exact_match_replace_dict_list["ui"] = "user interface"
        self.exact_match_replace_dict_list["mq"] = "message queue"
        self.exact_match_replace_dict_list["aliyun"] = "alibaba cloud"
        self.exact_match_replace_dict_list["ali-cloud"] = "alibaba cloud"

        self.partial_match_replace_dict_list["ms"] = "microsoft"
        self.partial_match_replace_dict_list["vm"] = "virtual machine"
        self.partial_match_replace_dict_list["website"] = "web"
        self.partial_match_replace_dict_list["test"] = "testing"
        self.partial_match_replace_dict_list["networking"] = "network"

        self.ExportMatchReplaceDictList()


test = TechStack()
job_skill = {}
nodeflair_file = open("nodeflair skill.txt", "r")
for nodeflair_skill in nodeflair_file:
    nodeflair_skill = nodeflair_skill.replace("\n", "")
    job_skill[nodeflair_skill] =nodeflair_skill
nodeflair_file.close()
troll = {}
result = test.GenerateLearningResource(troll, job_skill, "Google", "0")
print(result["Skill Learning Resource Remarks"])
test.ExportNotFoundSet()
